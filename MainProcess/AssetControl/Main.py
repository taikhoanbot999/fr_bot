import os
import subprocess
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from Core.Exchange.Exchange import ExchangeManager
from Core.Tracker.BitgetTracker import BitgetTracker
from Core.Tracker.GateIOTracker import GateIOTracker
from MainProcess.AssetControl.BalanceConfig import max_diff_rate
import Define
from Core.Tool import step, clear_console
from Core.Define import EXCHANGE, convert_exchange_to_name
from Core.AliveServiceClient import AliveServiceClient
from Define import transfer_done_file, SERVICE_NAME, root_path
from Core.Logger import log_info, LogService

start_time = time.time()

def asset_control_log(message):
    # Ghi log tập trung: shared.log + logs/asset/syslog.log
    log_info(LogService.ASSET, str(message))


class AssetProcess:

    MIN_ASSET_DIFF = max_diff_rate

    def __init__(self, binance_tracker, bitget_tracker):
        self.binance_tracker = binance_tracker
        self.bitget_tracker = bitget_tracker
        self.in_transfer = False  # Biến để kiểm tra xem có đang trong quá trình chuyển tiền hay không
        self.asset = {}
        self.process = None  # Biến để lưu trữ tiến trình chuyển tiền
        self.tick()


    def transfer(self, from_exchange, to_exchange, amount):
        if self.in_transfer:
            raise Exception("Transfer is already in progress, please wait until it completes.")
        self.in_transfer = True  # Đánh dấu là đang trong quá trình chuyển tiền

        # Ghi file transfer_done_file trạng thái WAIT + amount để API đọc được số tiền đang chuyển
        with open(transfer_done_file, 'w', encoding='utf-8') as f:
            f.write('WAIT\n')
            f.write(f'{amount}\n')
            f.write(f'{from_exchange}->{to_exchange}\n')  # thông tin nguồn -> đích (tham khảo)

        asset_control_log(f"Transfer {amount} USDT from {from_exchange} to {to_exchange}")
        # script_path = os.path.abspath("AssetControl/Transfer.py")
        script_path = f"{root_path}/code/MainProcess/AssetControl/Transfer/Transfer.py"
        venv_python = sys.executable
        self.process = subprocess.Popen(
            [venv_python, script_path, from_exchange, to_exchange, str(amount)],
            stdout=subprocess.PIPE,  # Không kế thừa stdout
            stderr=subprocess.PIPE,  # Không kế thừa stderr
        )


    def check_transfer_status(self):
        """
        Kiểm tra trạng thái chuyển tiền.
        Nếu quá trình chuyển tiền đã hoàn thành, trả về True, ngược lại trả về False.
        """
        with open(transfer_done_file, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            if first_line == 'OK':
                asset_control_log("Transfer completed successfully.")
                self.in_transfer = False
                return True
            elif first_line == 'ERROR':
                asset_control_log("Transfer failed, please check the logs for details.")
                self.in_transfer = False
                return True
            else:
                return False

    def tick(self):
        binance_asset_info = self.binance_tracker.get_cross_margin_account_info()
        bitget_asset_info = self.bitget_tracker.get_cross_margin_account_info()

        total = binance_asset_info.total_margin_balance + bitget_asset_info.total_margin_balance
        min_balance = total/2 - total* self.MIN_ASSET_DIFF
        self.asset = {
            'binance': binance_asset_info,
            'bitget': bitget_asset_info,
            'estimated_min_balance': min_balance,
        }

        if not self.in_transfer:
            # Nếu chênh lệch giữa 2 sàn quá 20% tổng asset thì chuyển lượng chênh lệch (làm tròn đến 10 USDT) từ sàn ít hơn sang sàn nhiều hơn
            total_asset = binance_asset_info.total_margin_balance + bitget_asset_info.total_margin_balance
            diff = abs(binance_asset_info.total_margin_balance - bitget_asset_info.total_margin_balance)
            if total_asset > 0 and diff / total_asset > self.MIN_ASSET_DIFF:
                move_amount = int(diff/2 // 10) * 10  # Làm tròn xuống đến 10 USDT
                if move_amount == 0:
                    raise ValueError("The difference is too small to transfer, please check your balances.")
                if binance_asset_info.total_margin_balance > bitget_asset_info.total_margin_balance:

                    self.transfer(convert_exchange_to_name(exchange1), convert_exchange_to_name(exchange2), move_amount)
                else:
                    self.transfer(convert_exchange_to_name(exchange2), convert_exchange_to_name(exchange1), move_amount)

        if self.in_transfer:
            self.check_transfer_status()

    def get_asset_info(self):
        return self.asset

    def get_status(self):
        return self.in_transfer


if __name__ == '__main__':

    clear_console()

    exchange1 = Define.exchange1
    exchange2 = Define.exchange2
    exchange_manager = ExchangeManager(exchange1, exchange2)
    asset_control_log("Starting asset balance process...")

    exchange1_tracker = None
    if exchange1 == EXCHANGE.BITGET:
        exchange1_tracker = BitgetTracker(exchange_manager.bitget_exchange)
    elif exchange1 == EXCHANGE.GATE:
        exchange1_tracker = GateIOTracker(exchange_manager.gate_exchange)

    exchange2_tracker = None
    if exchange2 == EXCHANGE.BITGET:
        exchange2_tracker = BitgetTracker(exchange_manager.bitget_exchange)
    elif exchange2 == EXCHANGE.GATE:
        exchange2_tracker = GateIOTracker(exchange_manager.gate_exchange)


    if exchange1_tracker is None or exchange2_tracker is None:
        asset_control_log(f"Invalid exchanges: {exchange1}, {exchange2}. Must be one of ['bitget', 'gate']")
        sys.exit(1)

    asset_process = AssetProcess(exchange1_tracker, exchange2_tracker)

    alive_service_client = AliveServiceClient(SERVICE_NAME.ASSET_CONTROL.value)

    try:

        while True:
            try:
                asset_process.tick()
            except Exception as e:
                asset_control_log(f"Error during asset process tick: {e}")
                time.sleep(5)

            # Draw positions table
            asset = asset_process.get_asset_info()
            status = asset_process.get_status()


            step_string1 = f"Binance: {asset['binance'].total_margin_balance} USDT"
            step_string2 = f"Bitget: {asset['bitget'].total_margin_balance} USDT"
            step_string3 = f"Estimated Min Balance: {asset['estimated_min_balance']} USDT"
            step_strings = [step_string1, step_string2, step_string3]
            if status :
                step_strings.append(f"Transfer in progress")

            step(step_strings)
            time.sleep(5)
    except KeyboardInterrupt:
        asset_control_log("Process interrupted by user (Ctrl+C). Exiting...")
