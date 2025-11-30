import json

from Core.Define import EXCHANGE
from Define import transfer_info_path



class TransferConfig:

    def __init__(self, from_exchange, to_exchange):
        self.from_exchange = from_exchange
        self.to_exchange = to_exchange

        self.binance_deposit_info = {}
        self.bitget_deposit_info = {}
        self.gate_deposit_info = {}

        self.load_config(from_exchange, to_exchange)


    def load_config(self, exchange1, exchange2):
        print(f"Loading configuration for exchanges: {exchange1}, {exchange2}")

        with open(transfer_info_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if exchange1 == EXCHANGE.BINANCE or exchange2 == EXCHANGE.BINANCE:
            binance_deposit_address = data.get('binance', {}).get('address', '')
            binance_deposit_chain = data.get('binance', {}).get('chain', '')
            binance_deposit_network = data.get('bitget', {}).get('network', '')

            print(f"Binance Deposit Address: {binance_deposit_address}")
            print(f"Binance Deposit Chain: {binance_deposit_chain}")
            print(f"Binance Deposit Network: {binance_deposit_network}")
            self.binance_deposit_info = {
                "address": binance_deposit_address,
                "chain": binance_deposit_chain,
                "network": binance_deposit_network
            }


        if exchange1 == EXCHANGE.BITGET or exchange2 == EXCHANGE.BITGET or exchange1 == EXCHANGE.BITGET_SUB or exchange2 == EXCHANGE.BITGET_SUB:
            bitget_deposit_address = data.get('bitget', {}).get('address', '')
            bitget_deposit_chain = data.get('bitget', {}).get('chain', '')
            bitget_deposit_network = data.get('bitget', {}).get('network', '')

            print(f"Bitget Deposit Address: {bitget_deposit_address}")
            print(f"Bitget Deposit Chain: {bitget_deposit_chain}")
            print(f"Bitget Deposit Network: {bitget_deposit_network}")
            self.bitget_deposit_info = {
                "address": bitget_deposit_address,
                "chain": bitget_deposit_chain,
                "network": bitget_deposit_network
            }

        if exchange1 == EXCHANGE.GATE or exchange2 == EXCHANGE.GATE:
            gate_deposit_address = data.get('gate', {}).get('address', '')
            gate_deposit_chain = data.get('gate', {}).get('chain', '')
            gate_deposit_network = data.get('gate', {}).get('network', '')

            print(f"Gate Deposit Address: {gate_deposit_address}")
            print(f"Gate Deposit Chain: {gate_deposit_chain}")
            print(f"Gate Deposit Network: {gate_deposit_network}")

            self.gate_deposit_info = {
                "address": gate_deposit_address,
                "chain": gate_deposit_chain,
                "network": gate_deposit_network
            }






