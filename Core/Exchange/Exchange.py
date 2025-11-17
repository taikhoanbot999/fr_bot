import ccxt
import ccxt.pro
import Config

from Core.Define import EXCHANGE

class ExchangeManager:
    def __init__(self, exchange1: EXCHANGE, exchange2: EXCHANGE):
        creds = Config.load_config(exchange1, exchange2)

        self.binance_exchange = ccxt.binanceusdm({
            'apiKey': creds['binance']['api_key'],
            'secret': creds['binance']['api_secret'],
            'enableRateLimit': True,
        })

        self.bitget_exchange = ccxt.bitget({
            'apiKey': creds['bitget']['api_key'],
            'secret': creds['bitget']['api_secret'],
            'password': creds['bitget']['password'],
            'enableRateLimit': True,
        })
        self.bitget_exchange.options['defaultType'] = 'swap'

        self.gate_exchange = ccxt.gateio({
            'apiKey': creds['gate']['api_key'],
            'secret': creds['gate']['api_secret'],
            'enableRateLimit': True,
        })
        self.gate_exchange.options['defaultType'] = 'swap'

        self.bitget_pro = ccxt.pro.bitget({
            'apiKey': creds['bitget']['api_key'],
            'secret': creds['bitget']['api_secret'],
            'password': creds['bitget']['password'],
            'options': {'defaultType': 'swap'}
        })

        self.gate_pro = ccxt.pro.gateio({
            'apiKey': creds['gate']['api_key'],
            'secret': creds['gate']['api_secret'],
            'uid': "22397301",
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap'
            }
        })