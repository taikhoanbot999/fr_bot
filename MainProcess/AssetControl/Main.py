import os
import subprocess
import sys
import time
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from fr_ccxt import CCXTWrapper
from Core.secret import get_secret
from Core.Tool import step, clear_console
from Core.Define import convert_exchange_to_name
from Define import transfer_done_file, SERVICE_NAME, code_dir, transfer_status_json_file, exchange1, exchange2
from Core.Logger import log_info, LogService
from MainProcess.AssetControl.BalanceConfig import max_diff_rate
from Core.Tracker.Tracker import AccountBalance

start_time = time.time()

def asset_control_log(message):
    # Ghi log tập trung: shared.log + logs/asset/syslog.log
    log_info(LogService.ASSET, str(message))


class AssetProcess:
    MIN_ASSET_DIFF = max_diff_rate

    def __init__(self, bitget_tracker, gate_tracker):
        self.bitget_tracker = bitget_tracker
        self.gate_tracker = gate_tracker
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
            f.write(f'{from_exchange}->{to_exchange}\n')

        # Ghi thêm JSON trạng thái để server ở container khác đọc được (atomic)
        try:
            tmp_path = transfer_status_json_file + '.tmp'
            payload = {
                'status': 'WAIT',
                'amount': float(amount),
                'from': from_exchange,
                'to': to_exchange,
                'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S')
            }
            with open(tmp_path, 'w', encoding='utf-8') as jf:
                json.dump(payload, jf, ensure_ascii=False)
            os.replace(tmp_path, transfer_status_json_file)
        except Exception as e:
            asset_control_log(f'Cannot write transfer_status.json: {e}')

        asset_control_log(f"Transfer {amount} USDT from {from_exchange} to {to_exchange}")
        script_path = os.path.join(code_dir, "MainProcess", "AssetControl", "Transfer", "Transfer.py")
        venv_python = sys.executable
        self.process = subprocess.Popen(
            [venv_python, script_path, from_exchange, to_exchange, str(amount)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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

    def _bitget_account_balance(self):
        resp = self.bitget_tracker.get_future_account_balance()
        usdt = resp["balances"].get("USDT", {"total": 0.0})
        total = float(usdt.get("total", 0.0))
        return AccountBalance(total, total, total, usdt.get("available", 0.0), 0.0)

    def _gate_account_balance(self):
        resp = self.gate_tracker.get_future_account_balance()
        usdt = resp["balances"].get("USDT", {"total": 0.0})
        total = float(usdt.get("total", 0.0))
        return AccountBalance(total, total, total, usdt.get("available", 0.0), 0.0)

    def tick(self):
        bitget_asset_info = self._bitget_account_balance()
        gate_asset_info = self._gate_account_balance()

        total = bitget_asset_info.total_margin_balance + gate_asset_info.total_margin_balance
        min_balance = total / 2 - total * self.MIN_ASSET_DIFF
        self.asset = {
            convert_exchange_to_name(exchange1): bitget_asset_info,
            convert_exchange_to_name(exchange2): gate_asset_info,
            'estimated_min_balance': min_balance,
        }

        if not self.in_transfer:
            # Nếu chênh lệch giữa 2 sàn quá 20% tổng asset thì chuyển lượng chênh lệch (làm tròn đến 10 USDT) từ sàn ít hơn sang sàn nhiều hơn
            total_asset = bitget_asset_info.total_margin_balance + gate_asset_info.total_margin_balance
            diff = abs(bitget_asset_info.total_margin_balance - gate_asset_info.total_margin_balance)
            if total_asset > 0 and diff / total_asset > self.MIN_ASSET_DIFF:
                move_amount = int(diff/2 // 10) * 10  # Làm tròn xuống đến 10 USDT
                if move_amount == 0:
                    raise ValueError("The difference is too small to transfer, please check your balances.")
                if bitget_asset_info.total_margin_balance > gate_asset_info.total_margin_balance:

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
    asset_control_log("Starting asset balance process...")

    api_info = get_secret()
    bitget_info = api_info['bitget']
    gate_info = api_info['gate']

    bitget_wrapper = CCXTWrapper(
        'bitget',
        apiKey=bitget_info['api_key'],
        secret=bitget_info['api_secret'],
        password=bitget_info['password'],
        options={'defaultType': 'swap'}
    )

    gate_wrapper = CCXTWrapper(
        'gate',
        apiKey=gate_info['api_key'],
        secret=gate_info['api_secret'],
        options={'defaultType': 'swap'}
    )

    asset_process = AssetProcess(bitget_wrapper, gate_wrapper)

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


            step_string1 = f"Bitget: {asset['bitget'].total_margin_balance} USDT"
            step_string2 = f"Gate: {asset['gate'].total_margin_balance} USDT"
            step_string3 = f"Estimated Min Balance: {asset['estimated_min_balance']} USDT"
            step_strings = [step_string1, step_string2, step_string3]
            if status :
                step_strings.append(f"Transfer in progress")

            step(step_strings)
            time.sleep(5)
    except KeyboardInterrupt:
        asset_control_log("Process interrupted by user (Ctrl+C). Exiting...")
