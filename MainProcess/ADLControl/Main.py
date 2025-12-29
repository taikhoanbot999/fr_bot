import asyncio
import copy
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
import ccxt
import ccxt.pro
from Core.Tool import try_this
from Define import exchange1, exchange2, root_path
from MainProcess.ADLControl.Log import adl_log
from MainProcess.ADLControl.Order import close_position_gate, close_position_bitget, fetch_position_bitget, \
    fetch_position_gate
import Config
from Core.Define import EXCHANGE


class ADLController:
    def __init__(self, bitget_exchange, gate_exchange, bitget_pro, gate_pro):

        self.bitget_pro = bitget_pro
        self.gate_pro = gate_pro

        self.bitget_exchange = bitget_exchange
        self.gate_exchange = gate_exchange

        self.lock = asyncio.Lock()
        self.positions = {}
        self.old_positions = {}
        self.error_count = 0


    def check_position_change(self, symbol):
        bitget_symbol = symbol.replace("OMNI", "OMNI1")
        bitget_total, bitget_side, bitget_contract_size = try_this(fetch_position_bitget,
                                                                   params={'bitget_exchange': self.bitget_exchange,
                                                                           'symbol': bitget_symbol},
                                                                   log_func=adl_log, retries=5, delay=1)
        gate_total, gate_side, gate_contract_size = try_this(fetch_position_gate,
                                                            params={'gate_exchange': self.gate_exchange,
                                                                    'symbol': symbol},
                                                            log_func=adl_log, retries=5, delay=1)

        if gate_total == 0 and bitget_total == 0:
            return

        adl_log(f"Gate total: {gate_total}, Bitget total: {bitget_total}, Symbol: {symbol}, Gate side: {gate_side}, Bitget side: {bitget_side}")

        if gate_total > bitget_total:
            diff = gate_total - bitget_total
            adl_log(f"Gate has more position: {diff} {symbol}")
            diff_contras = diff / gate_contract_size
            try:
                close_position_gate(self.gate_exchange, symbol, gate_side, diff_contras)
                adl_log(f"Closed position on GateIO: {symbol}, Size: {diff_contras} {gate_side}")
            except Exception as e:
                print(e)
                adl_log(f"Error closing position on GateIO: {e}")
        elif bitget_total > gate_total:
            diff = bitget_total - gate_total
            adl_log(f"Bitget has more position: {diff} {symbol}")
            diff_contras = diff / bitget_contract_size
            try:
                close_position_bitget(self.bitget_exchange, bitget_symbol, bitget_side, diff_contras)
                adl_log(f"Closed position on Bitget: {symbol}, Size: {diff_contras} {bitget_side}")
            except Exception as e:
                print(e)
                adl_log(f"Error closing position on Bitget: {e}")

    def check_position_change_by_ws(self):
        for p_symbol in self.positions.keys():
            if p_symbol not in self.old_positions.keys():
                adl_log(f"Position for {p_symbol} has been removed")
                continue

            old_bitget_size = self.old_positions[p_symbol].get('bitget_size', 0)
            old_gate_size = self.old_positions[p_symbol].get('gate_size', 0)

            new_bitget_size = self.positions[p_symbol].get('bitget_size', 0)
            new_gate_size = self.positions[p_symbol].get('gate_size', 0)

            if old_bitget_size != new_bitget_size or old_gate_size != new_gate_size:
                adl_log(f"Position changed for {p_symbol}: Bitget {old_bitget_size} -> {new_bitget_size}, GateIO {old_gate_size} -> {new_gate_size}")
                self.check_position_change(p_symbol)

    async def sync_hedge(self, exchange, symbols):
        await exchange.load_markets()
        adl_log(f"Listening for position changes on {exchange.id}...")

        self.error_count = 0

        while True:
            try:
                pos = await exchange.watch_positions(symbols=symbols)
                print(pos)

                async with self.lock:
                    self.old_positions = copy.deepcopy(self.positions)
                    # Check for symbols not present in current positions
                    current_symbols = {p['symbol'] for p in pos}
                    for symbol in self.positions.keys():
                        if symbol not in current_symbols:
                            if exchange.id == 'bitget':
                                adl_log(f"Bitget position for {symbol} is be size 0")
                                self.positions[symbol]['bitget_size'] = 0
                            elif exchange.id == 'gateio':
                                adl_log(f"GateIO position for {symbol} is be size 0")
                                self.positions[symbol]['gate_size'] = 0

                    for p in pos:
                        p_symbol = p['symbol']
                        p_size = float(p['contracts']) * float(p['contractSize'])
                        ignore_symbols = ["SXP", "OKB", "BGB", "EDEN", "ETH"]
                        if any(ig in p_symbol for ig in ignore_symbols):
                            continue

                        if exchange.id == 'bitget':
                            self.positions.setdefault(p_symbol, {})['bitget_size'] = p_size
                        elif exchange.id == 'gateio':
                            self.positions.setdefault(p_symbol, {})['gate_size'] = p_size

                    # Check for changes in positions
                    self.check_position_change_by_ws()
                    self.error_count = self.error_count - 1 if self.error_count > 1 else 0

            except Exception as e:
                self.error_count += 1
                adl_log(f"Lỗi khi sync: {e}")
                time.sleep(1)

    async def main(self):
        await self.gate_pro.load_markets()
        positions = await self.gate_pro.watch_positions()
        open_symbols = [p['symbol'] for p in positions if float(p.get('contracts', 0)) > 0]
        ignore_symbols = ["SXP", "OKB", "BGB", "EDEN", "ETH"]
        open_symbols = [s for s in open_symbols if not any(ig in s for ig in ignore_symbols)]
        with open(f"{root_path}/code/_settings/symbols.txt", 'w', encoding='utf-8') as file:
            for sym in open_symbols:
                file.write(f"{sym}\n")
        print(f"Start Adl with symbols: {open_symbols}")
        print(f"Start with symbols size: {len(open_symbols)}")
        await asyncio.gather(
            self.sync_hedge(self.gate_pro, open_symbols),
            self.sync_hedge(self.bitget_pro, open_symbols),
        )

if __name__ == '__main__':
    # Khởi tạo trực tiếp các instance ccxt/ccxt.pro thay vì dùng ExchangeManager
    creds = Config.get_credentials(exchange1, exchange2)

    # REST exchanges
    bitget_creds = creds['bitget']
    gate_creds = creds['gate']

    bitget_exchange = ccxt.bitget({
        'apiKey': bitget_creds['api_key'],
        'secret': bitget_creds['api_secret'],
        'password': bitget_creds['password'],
        'enableRateLimit': True,
    })
    bitget_exchange.options['defaultType'] = 'swap'

    gate_exchange = ccxt.gateio({
        'apiKey': gate_creds['api_key'],
        'secret': gate_creds['api_secret'],
        'enableRateLimit': True,
    })
    gate_exchange.options['defaultType'] = 'swap'

    # PRO exchanges (WebSocket)
    bitget_pro = ccxt.pro.bitget({
        'apiKey': bitget_creds['api_key'],
        'secret': bitget_creds['api_secret'],
        'password': bitget_creds['password'],
        'options': {'defaultType': 'swap'}
    })

    gate_pro = ccxt.pro.gateio({
        'apiKey': gate_creds['api_key'],
        'secret': gate_creds['api_secret'],
        'uid': "22397301",  # giữ nguyên uid như ExchangeManager cũ
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'}
    })

    adl_controller = ADLController(
        bitget_exchange=bitget_exchange,
        gate_exchange=gate_exchange,
        bitget_pro=bitget_pro,
        gate_pro=gate_pro,
    )
    asyncio.run(adl_controller.main())
