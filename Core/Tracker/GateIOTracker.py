from Core.Define import EXCHANGE
from Core.Tracker.Tracker import CcxtTracker
from Core.Define import PositionSide, Position, EXCHANGE
from Core.Tracker.Tracker import AccountBalance
class GateIOTracker(CcxtTracker):

        super().__init__(exchange_client=exchange, exchange=EXCHANGE.GATE)
    def __init__(self, exchange):
       self.client = exchange

    def _normalize_symbol_for_ticker(self, pos):
        """Chuyển contract GateIO (VD: BTC_USDT) về dạng fetch_ticker (BTC/USDT)."""
        contract = pos.get('info', {}).get('contract') or pos.get('symbol') or ''
        if '_' in contract:
            parts = contract.split('_')
            if len(parts) == 2 and parts[0] and parts[1]:
                return f"{parts[0]}/{parts[1]}"
        # Thử dạng chuẩn nếu có sẵn
        if '/' in contract:
            return contract
        return contract  # fallback trả nguyên

    def _get_current_price(self, pos):
        """Lấy current price ưu tiên mark/last có sẵn, fallback fetch_ticker."""
        # Ưu tiên dùng dữ liệu đã có trong pos
        for key in ('markPrice', 'lastPrice', 'indexPrice', 'last', 'mark'):
            try:
                v = pos.get(key)
                if v not in (None, '', 0, '0'):
                    price = float(v)
                    if price > 0:
                        return price
            except Exception:
                pass
        # Trong info
        info = pos.get('info', {}) or {}
        for key in ('markPrice', 'lastPrice', 'indexPrice', 'last', 'mark', 'close'):
            try:
                v = info.get(key)
                if v not in (None, '', 0, '0'):
                    price = float(v)
                    if price > 0:
                        return price
            except Exception:
                pass
        # fetch ticker nếu vẫn chưa có
        fetch_symbol = self._normalize_symbol_for_ticker(pos)
        try:
            ticker = self.client.fetch_ticker(fetch_symbol)
            for key in ('last', 'mark', 'close', 'ask', 'bid'):
                if key in ticker:
                    try:
                        val = float(ticker[key])
                        if val > 0:
                            return val
                    except Exception:
                        continue
            tinfo = ticker.get('info', {}) or {}
            for key in ('markPrice', 'lastPrice', 'close'):
                if key in tinfo:
                    try:
                        val = float(tinfo[key])
                        if val > 0:
                            return val
                    except Exception:
                        continue
        except Exception:
            pass
        return 0.0

    def get_open_positions(self):
        """
        Get all currently open positions on GateIO Futures.
        :return:
        """
        positions = []
        response = self.client.fetch_positions()
        positions_json = [pos for pos in response if float(pos['contracts']) > 0]
        for pos in positions_json:
            symbol_contract = pos['info']['contract']  # VD: BTC_USDT
            symbol = symbol_contract.replace('_', '')  # Giữ nguyên hành vi cũ cho Position

            # Skip SXP positions trước khi xử lý
            if symbol.startswith("SXP"):
                continue

            side = PositionSide.LONG if pos['side'].upper() == 'LONG' else PositionSide.SHORT
            try:
                margin = float(pos.get('maintenanceMargin')) if 'maintenanceMargin' in pos else 1.0
            except Exception:
                margin = 1.0
            # Dùng current price thay vì entryPrice theo yêu cầu
            try:
                entry_price = self._get_current_price(pos)
            except Exception:
                entry_price = 0.0
            position = Position(symbol=symbol, side=side, amount=float(pos['contracts']),
                                entry_price=entry_price, exchange=EXCHANGE.GATE, margin=margin)

            try:
                total_paid_funding = float(pos['info'].get('pnl_fund', 0.0))
            except Exception:
                total_paid_funding = 0.0
            position.set_paid_funding(total_paid_funding)
            positions.append(position)

        return positions
    def get_cross_margin_account_info(self):
        """
        Fetch cross margin account information and calculate ROI for each asset.
        :return:
        """
        account_info = self.client.fetchBalance(params={'unifiedAccount': True})
        info = account_info['info'][0]
        total_margin_balance = float(info['unified_account_total_equity'])
        total_initial_margin = 0
        total_maint_margin =0
        available_balance = 0
        unrealized_pnl = 0

        account_balance = AccountBalance(total_margin_balance,
                                         total_initial_margin,
                                         total_maint_margin,
                                         available_balance,
                                         unrealized_pnl)
        return account_balance

    def get_paid_funding(self, symbol, start_time):
        """
        Lấy tổng funding đã trả từ start_time cho đến hiện tại.
        """
        total_paid = 0.0
        end_time = self.client.milliseconds()
        symbol = symbol.replace('USDT', '_USDT')
        while True:
            try:
                funding_history = self.client.fetchFundingHistory(
                    symbol=symbol,
                    since=start_time,
                    limit=100,
                    end_time=end_time,
                    params={
                        'endTime': end_time,
                    }
                )
            except Exception as e:
                print(f"Lỗi lấy funding: {e}")
                break

            if not funding_history:
                break

            # Cộng funding
            out = False
            for f in funding_history:
                if f.get('timestamp', 0) < start_time:
                    out = True
                    break
                if f.get('timestamp', 0) > end_time:
                    out = True
                    break
                total_paid += float(f.get("amount", 0))
            if out:
                break

            # Lấy thời gian cuối cùng để tiếp tục
            end_time = funding_history[0].get("timestamp") - 1

            # Chờ nhẹ để tránh bị rate limit
            time.sleep(0.2)

        return total_paid