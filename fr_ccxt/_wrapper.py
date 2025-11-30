# fr_ccxt/_wrapper.py
"""
A small synchronous wrapper around ccxt exchanges to normalize futures account balances.
Supports: bitget, gate (and falls back to generic ccxt.fetch_balance behaviour).

Usage:
    from fr_ccxt import CCXTWrapper
    w = CCXTWrapper('bitget', apiKey='k', secret='s', password='p')
    bal = w.get_future_account_balance()

Return format:
{
    "exchange": "bitget",
    "raw": <raw ccxt response or exchange info>,
    "balances": {
        "USDT": {"total": 123.0, "available": 10.5},
        ...
    }
}
"""
from typing import Any, Dict
import ccxt


def _safe_float(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        return float(v)
    except Exception:
        return 0.0


class CCXTWrapper:
    """Synchronous wrapper for ccxt exchanges focusing on futures balances.

    Constructor accepts either an exchange id string (e.g. 'bitget', 'gate')
    or an already-instantiated ccxt exchange object.
    """

    def __init__(
        self,
        exchange: Any,
        apiKey: str | None = None,
        secret: str | None = None,
        password: str | None = None,
        options: dict | None = None,
        enableRateLimit: bool = True,
        **kwargs,
    ) -> None:
        # If an exchange instance is provided, use it directly
        if hasattr(exchange, "fetch_balance"):
            self._ex = exchange
            self.exchange_id = getattr(exchange, "id", "custom")
            return

        # Otherwise expect a string id
        if not isinstance(exchange, str):
            raise TypeError("exchange must be a ccxt exchange id string or an exchange instance")

        self.exchange_id = exchange.lower()
        ex_cls = getattr(ccxt, self.exchange_id, None)
        if ex_cls is None:
            raise ValueError(f"Exchange '{exchange}' not supported by ccxt in this environment")

        init_kwargs = {
            "apiKey": apiKey,
            "secret": secret,
            "password": password,
            "enableRateLimit": enableRateLimit,
        }
        if options:
            init_kwargs["options"] = options
        # include any other kwargs (like proxy, uid...)
        init_kwargs.update(kwargs)

        self._ex = ex_cls(**{k: v for k, v in init_kwargs.items() if v is not None})

    def _parse_common_ccxt_balance(self, balance: dict) -> Dict[str, Dict[str, float]]:
        """Parse balance returned by ccxt.fetch_balance() which commonly has 'total' and 'free' dicts."""
        balances: Dict[str, Dict[str, float]] = {}
        totals = balance.get("total") or {}
        frees = balance.get("free") or {}
        # sometimes ccxt returns nested structure where currencies are keys
        if isinstance(totals, dict):
            for cur, tot in totals.items():
                total = _safe_float(tot)
                free = _safe_float(frees.get(cur))
                balances[cur] = {"total": total, "available": free}
            return balances
        # fallback: try to extract from balance directly
        for k, v in balance.items():
            if k in ("info", "timestamp", "datetime"):
                continue
            if isinstance(v, dict) and ("total" in v or "free" in v):
                total = _safe_float(v.get("total"))
                free = _safe_float(v.get("free") or v.get("available"))
                balances[k] = {"total": total, "available": free}
        return balances

    def _parse_info_like_list(self, info: Any) -> Dict[str, Dict[str, float]]:
        """Try to parse exchange-specific 'info' payloads where balances appear in a list.
        This handles common shapes like [{'currency': 'USDT', 'available': '1', 'balance': '2'}, ...]
        """
        balances: Dict[str, Dict[str, float]] = {}
        if not info:
            return balances
        # If info is a dict with a 'data' list, dive into it
        if isinstance(info, dict):
            candidate = None
            if "data" in info and isinstance(info["data"], list):
                candidate = info["data"]
            elif "balances" in info and isinstance(info["balances"], list):
                candidate = info["balances"]
            else:
                # maybe info itself is the list-like under some key
                for k, v in info.items():
                    if isinstance(v, list):
                        candidate = v
                        break
            if candidate is None:
                # not list-like, try to parse keys that look like currencies
                for k, v in info.items():
                    if isinstance(v, dict):
                        total = _safe_float(v.get("balance") or v.get("total") or v.get("equity"))
                        free = _safe_float(v.get("available") or v.get("free") or v.get("availableBalance"))
                        if total or free:
                            balances[k.upper()] = {"total": total, "available": free}
                return balances
            info_list = candidate
        elif isinstance(info, list):
            info_list = info
        else:
            return balances

        for item in info_list:
            if not isinstance(item, dict):
                continue
            # try common keys
            cur = item.get("currency") or item.get("coin") or item.get("asset") or item.get("symbol") or item.get("coinId")
            if cur is None:
                # sometimes it's 'currency' nested under other keys
                for k in ("symbol", "asset", "coin", "token"):
                    if k in item:
                        cur = item.get(k)
                        break
            if cur is None:
                continue
            cur = str(cur).upper()
            total = _safe_float(item.get("balance") or item.get("total") or item.get("equity") or item.get("availableBalance"))
            free = _safe_float(item.get("available") or item.get("free") or item.get("availableBalance") or item.get("balanceAvailable"))
            balances[cur] = {"total": total, "available": free}
        return balances

    def get_future_account_balance(self) -> Dict[str, Any]:
        """Fetch and normalize futures account balance.

        Strategy:
        - Try to call fetch_balance with a 'type' hint for futures (params)
        - If that fails, call fetch_balance() without params
        - Normalize using common ccxt shape (total/free) or try to parse 'info' for list-like payloads
        """
        # attempt to fetch balance with a param hint many exchanges use
        params_options = [
            {"type": "future"},
            {"type": "futures"},
            {"type": "swap"},
            {},
        ]

        last_exc = None
        balance_resp = None
        for params in params_options:
            try:
                # Some ccxt implementations accept params as keyword arg
                balance_resp = self._ex.fetch_balance(params=params) if params else self._ex.fetch_balance()
                break
            except Exception as e:
                last_exc = e
                # try next params hint
                continue

        if balance_resp is None:
            # nothing worked
            raise last_exc if last_exc is not None else RuntimeError("Failed to fetch balance")

        # balance_resp is typically a dict with keys: info, total, free, used, etc.
        balances: Dict[str, Dict[str, float]] = {}
        try:
            # first, try the common ccxt shape
            balances = self._parse_common_ccxt_balance(balance_resp)
            if not balances:
                # try parsing info
                info = balance_resp.get("info") or balance_resp
                balances = self._parse_info_like_list(info)
        except Exception:
            # fallback parsing
            try:
                info = balance_resp.get("info") or balance_resp
                balances = self._parse_info_like_list(info)
            except Exception:
                balances = {}

        return {"exchange": self.exchange_id, "raw": balance_resp, "balances": balances}

