import threading
import time

from pydantic import BaseModel, Field

from Server.ServiceManager.MicroserviceManager import MicroserviceManager
from Core.Define import convert_exchange_to_name
from Core.Exchange.Exchange import ExchangeManager

class AppCore:
    def __init__(self):
        self.microservice_manager = MicroserviceManager()
        self.run()

    def get_microservices(self):
        services =  self.microservice_manager.get_microservices()
        return [ms.get_model() for ms in services]

    def start_microservice(self, service_id):
        return self.microservice_manager.start_microservice(service_id)

    def stop_microservice(self, service_id):
        return self.microservice_manager.stop_microservice(service_id)

    def main_loop(self):
        while True:
            for microservice in self.microservice_manager.get_microservices():
                microservice.ping()
            time.sleep(5)

    def run(self):
        main_thread = threading.Thread(target=self.main_loop)
        main_thread.start()

    def _to_bitget_symbol(self, internal_symbol: str) -> str:
        # internal like BTCUSDT -> BTC/USDT:USDT
        if internal_symbol.endswith('USDT') and '/' not in internal_symbol:
            base = internal_symbol[:-4]
            return f"{base}/USDT:USDT"
        return internal_symbol

    def _to_gate_symbol(self, internal_symbol: str) -> str:
        # Gate USDT-margined perpetuals use BASE/USDT:USDT in ccxt
        if internal_symbol.endswith('USDT') and '/' not in internal_symbol:
            base = internal_symbol[:-4]
            return f"{base}/USDT:USDT"
        # If already a pair without :USDT, append it to force swap contract
        if "/USDT" in internal_symbol and ":USDT" not in internal_symbol:
            return internal_symbol + ":USDT"
        return internal_symbol

    def _normalize_swap_symbol(self, symbol: str) -> str:
        """Return a swap contract symbol like BTC/USDT:USDT if not already normalized."""
        if '/' in symbol and ':USDT' in symbol:
            return symbol
        if symbol.endswith('USDT'):
            base = symbol[:-4]
            return f"{base}/USDT:USDT"
        return symbol

