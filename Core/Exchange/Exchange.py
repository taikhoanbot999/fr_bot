import ccxt
import ccxt.pro
import Config
import threading

from Core.Define import EXCHANGE

# ExchangeManager đã được loại bỏ. Các module khác nên khởi tạo trực tiếp ccxt/ccxt.pro
# sử dụng Config.get_credentials(exchange1, exchange2).

# File này được giữ lại để tránh import lỗi nếu còn module legacy bên ngoài repo,
# nhưng class ExchangeManager không còn tồn tại.
