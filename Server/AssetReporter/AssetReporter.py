import json
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from Core.Exchange.Exchange import ExchangeManager
from Core.Tracker.BitgetTracker import BitgetTracker
from Core.Tracker.GateIOTracker import GateIOTracker
from Core.Define import EXCHANGE
from Define import exchange1, exchange2, log_path, transfer_done_file


class AssetReporter:
    """
    Periodically snapshot total assets from the two configured exchanges and
    append them to a JSONL report file under logs/asset_report.jsonl
    """

    SCHEDULE_HOURS = [0, 4, 8, 12, 16]

    def __init__(self, report_file: Optional[str] = None):
        self.report_file = report_file or os.path.join(log_path, "asset_report.jsonl")
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.report_file), exist_ok=True)

        # Build exchange manager and trackers once for reuse
        self.exchange_manager = ExchangeManager(exchange1, exchange2)
        self.tracker1 = self._build_tracker(exchange1)
        self.tracker2 = self._build_tracker(exchange2)

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._scheduler_loop, name="AssetReporterScheduler", daemon=True)
        self._thread.start()

    def _build_tracker(self, ex: EXCHANGE):
        """Create a tracker instance for the given exchange enum. Returns None if unsupported."""
        try:
            if ex == EXCHANGE.BITGET or ex == EXCHANGE.BITGET_SUB:
                return BitgetTracker(self.exchange_manager.bitget_exchange)
            if ex == EXCHANGE.GATE:
                return GateIOTracker(self.exchange_manager.gate_exchange)
            # Not implemented trackers (BINANCE, BYBIT, OKX) -> None
            return None
        except Exception:
            return None

    def stop(self):
        self._stop_event.set()
        try:
            if self._thread.is_alive():
                self._thread.join(timeout=1)
        except Exception:
            pass

    def _next_run_at(self, now: datetime) -> datetime:
        candidates: List[datetime] = []
        for h in self.SCHEDULE_HOURS:
            candidates.append(now.replace(hour=h, minute=0, second=0, microsecond=0))
        # if all candidates <= now, use tomorrow's earliest
        future = [dt for dt in candidates if dt > now]
        if future:
            return min(future)
        # tomorrow first schedule hour
        tomorrow = (now + timedelta(days=1)).replace(hour=self.SCHEDULE_HOURS[0], minute=0, second=0, microsecond=0)
        return tomorrow

    def _scheduler_loop(self):
        # Sleep a short moment to avoid clashing with server startup
        time.sleep(2)
        while not self._stop_event.is_set():
            now = datetime.now()
            next_at = self._next_run_at(now)
            # Sleep in short intervals to be interruptible
            while not self._stop_event.is_set():
                now = datetime.now()
                if now >= next_at:
                    try:
                        self.take_snapshot()
                    except Exception:
                        # Swallow exceptions to keep the loop alive
                        pass
                    # compute next
                    break
                # sleep up to 30s granularity
                remain = (next_at - now).total_seconds()
                # Ép về int để tránh cảnh báo kiểu so sánh int/float
                remain_int = int(remain)
                time.sleep(min(30, max(1, remain_int)))

    def _safe_float(self, v) -> float:
        try:
            return float(v)
        except Exception:
            return 0.0

    def _get_balances(self) -> Dict[str, float]:
        # For each side, fetch total_margin_balance if tracker available
        side1 = 0.0
        side2 = 0.0
        try:
            if self.tracker1 is not None:
                info1 = self.tracker1.get_cross_margin_account_info()
                side1 = self._safe_float(getattr(info1, 'total_margin_balance', 0.0))
        except Exception:
            side1 = 0.0
        try:
            if self.tracker2 is not None:
                info2 = self.tracker2.get_cross_margin_account_info()
                side2 = self._safe_float(getattr(info2, 'total_margin_balance', 0.0))
        except Exception:
            side2 = 0.0
        return {"side1": side1, "side2": side2, "total": side1 + side2}

    def _get_transfer_inflight(self) -> float:
        """Đọc file transfer_done.txt để lấy amount đang chuyển (chỉ khi trạng thái WAIT)."""
        try:
            if not os.path.exists(transfer_done_file):
                return 0.0
            with open(transfer_done_file, 'r', encoding='utf-8') as f:
                status = f.readline().strip()
                if status != 'WAIT':
                    return 0.0
                amount_line = f.readline().strip()
                return self._safe_float(amount_line)
        except Exception:
            return 0.0

    def take_snapshot(self) -> Dict[str, Any]:
        ts = datetime.now().isoformat(timespec='seconds')
        balances = self._get_balances()
        record = {
            "timestamp": ts,
            "side1": balances["side1"],
            "side2": balances["side2"],
            "total": balances["total"],
        }
        # Append to JSONL file
        try:
            with open(self.report_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            # If write fails, ignore but still return
            pass
        return record

    def get_report(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not os.path.exists(self.report_file):
            return []
        records: List[Dict[str, Any]] = []
        try:
            with open(self.report_file, 'r', encoding='utf-8') as f:
                if limit and limit > 0:
                    # Read last N lines efficiently
                    records = self._tail_jsonl(f, limit)
                else:
                    records = [json.loads(line) for line in f if line.strip()]
        except Exception:
            records = []
        # Sort by timestamp ascending
        try:
            records.sort(key=lambda r: r.get('timestamp', ''))
        except Exception:
            pass
        return records

    def _tail_jsonl(self, file_obj, limit: int) -> List[Dict[str, Any]]:
        # Simple tail implementation: read all, then slice. For small files this is fine.
        try:
            lines = file_obj.readlines()
            sliced = lines[-limit:]
            return [json.loads(line) for line in sliced if line.strip()]
        except Exception:
            return []

    # New: get the current balances instantly without writing to the report file
    def get_current(self) -> Dict[str, Any]:
        ts = datetime.now().isoformat(timespec='seconds')
        balances = self._get_balances()
        transfer_amount = self._get_transfer_inflight()
        total_with_transfer = balances['total'] + transfer_amount
        return {
            "timestamp": ts,
            "side1": balances["side1"],
            "side2": balances["side2"],
            "total": balances["total"],
            "transfer_inflight": transfer_amount,
            "total_with_transfer": total_with_transfer,
        }
