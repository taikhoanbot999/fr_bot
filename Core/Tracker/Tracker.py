import time

from Core.Define import Position, PositionSide, EXCHANGE


class AccountBalance:
    def __init__(self, total_margin_balance, total_initial_margin, total_maint_margin, available_balance, unrealized_pnl):
        self.total_margin_balance = total_margin_balance
        self.total_initial_margin = total_initial_margin
        self.total_maint_margin = total_maint_margin
        self.margin_level = self.total_margin_balance / self.total_initial_margin if self.total_initial_margin > 0 else 0
        self.maint_margin_coverage = self.total_margin_balance / self.total_maint_margin if self.total_maint_margin > 0 else 0
        self.available_balance = available_balance
        self.unrealized_pnl = unrealized_pnl

    def __repr__(self):
        return (f"AccountBalance(total_margin_balance={self.total_margin_balance}, "
                f"total_initial_margin={self.total_initial_margin}, "
                f"total_maint_margin={self.total_maint_margin}, "
                f"margin_level={self.margin_level}, "
                f"maint_margin_coverage={self.maint_margin_coverage}, "
                f"available_balance={self.available_balance}, "
                f"unrealized_pnl={self.unrealized_pnl})")


class Tracker:
    def __init__(self):
        """
        Initialize the Tracker with a ccxt Binance client.
        """
        self.client = None  # This should be set in subclasses

    def get_open_positions(self):
        """
        Get all currently open positions on Binance Futures.

        Returns:
            List of open positions (Position objects)
        """
        raise NotImplementedError("This method should be implemented in subclasses")

    def get_cross_margin_account_info(self):
        """
        Fetch cross margin account information and calculate ROI for each asset.

        Returns:
            AccountBalance object with account details
        """
        raise NotImplementedError("This method should be implemented in subclasses")


class CcxtTracker(Tracker):
    def __init__(self, exchange_client, exchange: EXCHANGE):
        super().__init__()
        self.client = exchange_client
        self.exchange = exchange

    def get_open_positions(self):
        if self.exchange in (EXCHANGE.BITGET, EXCHANGE.BITGET_SUB):
            return self._bitget_open_positions()
        if self.exchange == EXCHANGE.GATE:
            return self._gate_open_positions()
        raise NotImplementedError(f"Exchange {self.exchange} chưa được hỗ trợ trong tracker chung")

    def get_cross_margin_account_info(self):
        if self.exchange in (EXCHANGE.BITGET, EXCHANGE.BITGET_SUB):
            return self._bitget_cross_margin_info()
        if self.exchange == EXCHANGE.GATE:
            return self._gate_cross_margin_info()
        raise NotImplementedError(f"Exchange {self.exchange} chưa được hỗ trợ trong tracker chung")

    def get_paid_funding(self, symbol, start_time):
        if self.exchange in (EXCHANGE.BITGET, EXCHANGE.BITGET_SUB):
            return self._bitget_paid_funding(symbol, start_time)
        if self.exchange == EXCHANGE.GATE:
            return self._gate_paid_funding(symbol, start_time)
        raise NotImplementedError(f"Exchange {self.exchange} chưa được hỗ trợ trong tracker chung")

    def _bitget_open_positions(self):
        positions = []
        response = self.client.fetch_positions()
        for pos in response:
            info = pos.get('info', {}) or {}
            symbol = info.get('symbol') or pos.get('symbol') or ''
            if self._should_skip_symbol(symbol):
                continue
            side = PositionSide.LONG if str(pos.get('side', '')).upper() == 'LONG' else PositionSide.SHORT
            leverage = self._safe_inverse(pos.get('initialMarginPercentage'))
            contracts = self._safe_float(pos.get('contracts'))
            entry_price = self._bitget_current_price(symbol, pos)
            position = Position(symbol=symbol,
                                side=side,
                                amount=contracts,
                                entry_price=entry_price,
                                exchange=self.exchange,
                                margin=leverage)
            raw_total_fee = info.get('totalFee')
            position.set_paid_funding(self._safe_float(raw_total_fee))
            positions.append(position)
        return positions

    def _gate_open_positions(self):
        positions = []
        response = self.client.fetch_positions()
        for pos in response:
            contracts = self._safe_float(pos.get('contracts'))
            if contracts <= 0:
                continue
            info = pos.get('info', {}) or {}
            contract = info.get('contract') or pos.get('symbol') or ''
            symbol = contract.replace('_', '')
            if self._should_skip_symbol(symbol):
                continue
            side = PositionSide.LONG if str(pos.get('side', '')).upper() == 'LONG' else PositionSide.SHORT
            margin = self._safe_float(pos.get('maintenanceMargin'), default=1.0) or 1.0
            entry_price = self._gate_current_price(pos)
            position = Position(symbol=symbol,
                                side=side,
                                amount=contracts,
                                entry_price=entry_price,
                                exchange=self.exchange,
                                margin=margin)
            position.set_paid_funding(self._safe_float(info.get('pnl_fund')))
            positions.append(position)
        return positions

    def _bitget_cross_margin_info(self):
        params = {'productType': 'USDT-FUTURES'}
        account_info = self.client.fetchBalance(params)
        info = account_info['info'][0]
        return AccountBalance(
            total_margin_balance=float(info['unionTotalMargin']),
            total_initial_margin=float(info['accountEquity']),
            total_maint_margin=float(info['accountEquity']),
            available_balance=float(info['available']),
            unrealized_pnl=float(info['unrealizedPL'])
        )

    def _gate_cross_margin_info(self):
        account_info = self.client.fetchBalance(params={'unifiedAccount': True})
        info = account_info['info'][0]
        return AccountBalance(
            total_margin_balance=float(info['unified_account_total_equity']),
            total_initial_margin=0.0,
            total_maint_margin=0.0,
            available_balance=0.0,
            unrealized_pnl=0.0
        )

    def _bitget_paid_funding(self, symbol, start_time):
        total_paid = 0.0
        end_time = self.client.milliseconds()
        while True:
            try:
                funding_history = self.client.fetchFundingHistory(
                    symbol=symbol,
                    since=start_time,
                    limit=100,
                    params={'endTime': end_time}
                )
            except Exception:
                break
            if not funding_history:
                break
            for record in funding_history:
                total_paid += self._safe_float(record.get("amount"))
            end_time = funding_history[0].get("timestamp", end_time) - 1
            time.sleep(0.2)
        return total_paid

    def _gate_paid_funding(self, symbol, start_time):
        total_paid = 0.0
        end_time = self.client.milliseconds()
        gate_symbol = symbol if '_' in symbol else symbol.replace('USDT', '_USDT')
        while True:
            try:
                funding_history = self.client.fetchFundingHistory(
                    symbol=gate_symbol,
                    since=start_time,
                    limit=100,
                    end_time=end_time,
                    params={'endTime': end_time}
                )
            except Exception:
                break
            if not funding_history:
                break
            stop = False
            for record in funding_history:
                timestamp = record.get('timestamp', 0)
                if timestamp < start_time or timestamp > end_time:
                    stop = True
                    break
                total_paid += self._safe_float(record.get("amount"))
            if stop:
                break
            end_time = funding_history[0].get("timestamp", end_time) - 1
            time.sleep(0.2)
        return total_paid

    def _bitget_current_price(self, symbol, pos):
        price = self._extract_price(pos, ('markPrice', 'lastPrice', 'indexPrice'))
        if price:
            return price
        info = pos.get('info', {}) or {}
        price = self._extract_price(info, ('markPrice', 'lastPrice', 'indexPrice'))
        if price:
            return price
        return self._fetch_ticker_price(symbol)

    def _gate_current_price(self, pos):
        price = self._extract_price(pos, ('markPrice', 'lastPrice', 'indexPrice', 'last', 'mark'))
        if price:
            return price
        info = pos.get('info', {}) or {}
        price = self._extract_price(info, ('markPrice', 'lastPrice', 'indexPrice', 'last', 'mark', 'close'))
        if price:
            return price
        fetch_symbol = self._normalize_gate_symbol_for_ticker(pos)
        return self._fetch_ticker_price(fetch_symbol)

    def _fetch_ticker_price(self, symbol):
        if not symbol:
            return 0.0
        try:
            ticker = self.client.fetch_ticker(symbol)
        except Exception:
            return 0.0
        price = self._extract_price(ticker, ('last', 'mark', 'close', 'ask', 'bid'))
        if price:
            return price
        info = ticker.get('info', {}) or {}
        return self._extract_price(info, ('markPrice', 'lastPrice', 'close')) or 0.0

    def _extract_price(self, source, keys):
        if not source:
            return 0.0
        for key in keys:
            try:
                value = source.get(key)
                if value not in (None, '', 0, '0'):
                    price = float(value)
                    if price > 0:
                        return price
            except Exception:
                continue
        return 0.0

    def _normalize_gate_symbol_for_ticker(self, pos):
        info = pos.get('info', {}) or {}
        contract = info.get('contract') or pos.get('symbol') or ''
        if '_' in contract:
            base, quote = contract.split('_', 1)
            if base and quote:
                return f"{base}/{quote}"
        if '/' in contract:
            return contract
        return contract

    def _safe_float(self, value, default=0.0):
        try:
            if value in (None, ''):
                return default
            return float(value)
        except Exception:
            return default

    def _safe_inverse(self, value):
        try:
            val = float(value)
            if val > 0:
                return 1.0 / val
        except Exception:
            pass
        return 0.0  

    def _should_skip_symbol(self, symbol):
        return symbol.startswith('SXP')
