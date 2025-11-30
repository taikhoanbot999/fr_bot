import unittest
from fr_ccxt import CCXTWrapper


class DummyExchange:
    """Simple exchange stub that mimics ccxt fetch_balance behaviour."""

    id = "dummy"

    def __init__(self, responses):
        # responses is a list of dicts or Exceptions that fetch_balance will emit sequentially
        self._responses = list(responses)
        self.call_count = 0

    def fetch_balance(self, params=None):
        if not self._responses:
            raise RuntimeError("No more responses prepared")
        self.call_count += 1
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class TestCCXTWrapper(unittest.TestCase):
    def test_get_future_account_balance_common_shape(self):
        exchange = DummyExchange([
            {"total": {"USDT": "2.5"}, "free": {"USDT": "1.5"}},
        ])
        wrapper = CCXTWrapper(exchange)

        result = wrapper.get_future_account_balance()

        self.assertEqual(result["exchange"], "dummy")
        self.assertIn("USDT", result["balances"])
        self.assertAlmostEqual(result["balances"]["USDT"]["total"], 2.5)
        self.assertAlmostEqual(result["balances"]["USDT"]["available"], 1.5)

    def test_get_future_account_balance_info_list_fallback(self):
        info_payload = {
            "data": [
                {"currency": "USDT", "balance": "3", "available": "1"},
                {"currency": "BTC", "balance": "0.01", "available": "0.005"},
            ]
        }
        exchange = DummyExchange([
            {"info": info_payload},
        ])
        wrapper = CCXTWrapper(exchange)

        result = wrapper.get_future_account_balance()

        self.assertAlmostEqual(result["balances"]["USDT"]["total"], 3.0)
        self.assertAlmostEqual(result["balances"]["BTC"]["available"], 0.005)

    def test_get_future_account_balance_retries_params(self):
        # first call raises, second succeeds (simulating unsupported params then fallback)
        exchange = DummyExchange([
            RuntimeError("type not supported"),
            {"total": {"USDT": 1}, "free": {"USDT": 0.4}},
        ])
        wrapper = CCXTWrapper(exchange)

        result = wrapper.get_future_account_balance()

        self.assertEqual(exchange.call_count, 2)
        self.assertAlmostEqual(result["balances"]["USDT"]["total"], 1.0)
        self.assertAlmostEqual(result["balances"]["USDT"]["available"], 0.4)


if __name__ == "__main__":
    unittest.main()

