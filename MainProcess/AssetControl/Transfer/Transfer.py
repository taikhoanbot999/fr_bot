import os.path
import sys
import time
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from Core.Exchange.Exchange import ExchangeManager
from TransferConfig import TransferConfig
from Core.Define import EXCHANGE
from Define import transfer_done_file, exchange2, exchange1, transfer_status_json_file
from Core.Tool import try_this
from Core.Logger import log_info, LogService, LogTarget


exchange_manager = ExchangeManager(exchange1, exchange2)
bitget = exchange_manager.bitget_exchange
binance = exchange_manager.binance_exchange
gate = exchange_manager.gate_exchange

start_time = time.time()


def tunel_log(message):
    # Chỉ ghi vào service log (logs/tunel/syslog.log); không ghi shared, không ghi Discord
    log_info(LogService.TUNEL, str(message), target=LogTarget.SERVICE)


def transfer_swap_to_spot(exchange, amount):
    if exchange == EXCHANGE.BINANCE:
        transfer = binance.transfer(code='USDT', amount=amount, fromAccount='swap', toAccount='spot')
        tunel_log(transfer)
    elif exchange == EXCHANGE.BITGET:
        transfer = bitget.transfer(code='USDT', amount=amount, fromAccount='swap', toAccount='spot')
        tunel_log(transfer)
    elif exchange == EXCHANGE.GATE:
        # unified account
        tunel_log("Gate is unified account, no need to transfer from swap to spot.")
    else:
        raise ValueError("Unsupported exchange for transfer to spot account.")


def with_draw_from_spot(f_exchange, t_exchange, amount):
    if f_exchange == EXCHANGE.BINANCE and t_exchange == EXCHANGE.BITGET:
        withdraw = binance.withdraw(code='USDT', amount=amount, address=transfer_config.bitget_deposit_info['address'],
                                    params={'chain': transfer_config.bitget_deposit_info['chain'], 'network': transfer_config.bitget_deposit_info['network']})
        tunel_log(withdraw)
        return withdraw['id']

    elif f_exchange == EXCHANGE.BITGET and t_exchange == EXCHANGE.BINANCE:
        withdraw = bitget.withdraw(code='USDT', amount=amount, address=transfer_config.binance_deposit_info['address'],
                                   params={'chain': transfer_config.binance_deposit_info['chain'], 'network': transfer_config.binance_deposit_info['network']})
        tunel_log(withdraw)
        return withdraw['id']

    elif f_exchange == EXCHANGE.GATE and t_exchange == EXCHANGE.BITGET:
        withdraw = gate.withdraw(code='USDT', amount=amount, address=transfer_config.bitget_deposit_info['address'],
                                 params={'chain': transfer_config.bitget_deposit_info['chain'], 'network': transfer_config.bitget_deposit_info['network']})
        tunel_log(withdraw)
        return withdraw['id']

    elif f_exchange == EXCHANGE.BITGET and t_exchange == EXCHANGE.GATE:
        print(f"network: {transfer_config.gate_deposit_info['network']}")
        print(f"chain: {transfer_config.gate_deposit_info['chain']}")
        print(f"address: {transfer_config.gate_deposit_info['address']}")
        withdraw = bitget.withdraw(code='USDT', amount=amount, address=transfer_config.gate_deposit_info['address'],
                                   params={'chain': transfer_config.gate_deposit_info['chain'], 'network': transfer_config.gate_deposit_info['network']})
        tunel_log(withdraw)
        return withdraw['id']
    else:
        raise ValueError("Unsupported exchange for withdrawal from spot account.")


def get_withdrawal_txid(exchange, order_id):
    """
    Get the transaction ID of a withdrawal by its order ID.

    :param exchange: The exchange to fetch the withdrawal from.
    :param order_id: The order ID of the withdrawal.
    :return: The transaction ID if found, otherwise None.
    """
    if exchange == EXCHANGE.BINANCE:
        withdrawals = binance.fetchWithdrawals(code='USDT', params={'limit': 10})
    elif exchange == EXCHANGE.BITGET or exchange == EXCHANGE.BITGET_SUB:
        withdrawals = bitget.fetchWithdrawals(code='USDT', params={'limit': 10})
    elif exchange == EXCHANGE.GATE:
        withdrawals = gate.fetchWithdrawals(code='USDT', params={'limit': 10})
    else:
        raise ValueError("Unsupported exchange for fetching withdrawal txid.")

    for item in withdrawals:
        if item['id'] == order_id:
            if item.get('status') == 'pending':
                raise Exception("withdrawal is still pending, please wait.")
            if item.get('txid', None) is None:
                raise Exception("withdrawal txid is not available yet, please wait.")
            return item.get('txid', None)
    raise Exception("Withdrawal with the given order ID not found.")


def get_withdraw_txid(order_id):
    """
    Get the transaction ID of a withdrawal by its order ID.

    :param order_id: The order ID of the withdrawal.
    :return: The transaction ID if found, otherwise None.
    """
    try:
        withdrawal = bitget.fetchWithdrawals(code='USDT', params={'limit': 10})
        if not withdrawal:
            raise Exception("No withdrawal found with the given order ID.")
        for item in withdrawal:
            if item['id'] == order_id:
                return item.get('txid', None)
        raise Exception("Withdrawal with the given order ID not found.")
    except Exception as e:
        raise Exception(f"Error fetching withdrawal txid: {e}")


def wait_for_desposit(exchange, txid):
    """
    Chờ đợi giao dịch nạp tiền thành công trên Bitget.

    :param exchange: Sàn giao dịch để theo dõi giao dịch nạp tiền.
    :param txid: Mã giao dịch cần theo dõi.
    """
    try:
        if exchange == EXCHANGE.BINANCE:
            deposits = binance.fetchDeposits(code='USDT', limit=10, params={'network': transfer_config.binance_deposit_info['network']})
        elif exchange == EXCHANGE.BITGET or exchange == EXCHANGE.BITGET_SUB:
            deposits = bitget.fetchDeposits(code='USDT', limit=10, params={'network': transfer_config.bitget_deposit_info['network']})
        elif exchange == EXCHANGE.GATE:
            deposits = gate.fetchDeposits(code='USDT', limit=10, params={'network': transfer_config.gate_deposit_info['network']})
        else:
            raise ValueError("Unsupported exchange for waiting deposit.")
        for deposit in deposits:
            if deposit['txid'] == txid:
                return True

        raise Exception(f"Deposit with txid {txid} not found.")
    except Exception as e:
        raise Exception(f"Error fetching deposits: {e}")


def transfer_spot_to_swap(exchange, amount):
    """
    Chuyển tiền từ tài khoản spot sang tài khoản swap trên sàn giao dịch.

    :param exchange: Sàn giao dịch để thực hiện chuyển tiền.
    :param amount: Số lượng tiền cần chuyển.
    """
    if exchange == EXCHANGE.BINANCE:
        transfer = binance.transfer(code='USDT', amount=amount, fromAccount='spot', toAccount='swap')
        tunel_log(transfer)
    elif exchange == EXCHANGE.BITGET:
        amount = amount - 0.04  # trừ phí rút trên APTOS
        transfer = bitget.transfer(code='USDT', amount=amount, fromAccount='spot', toAccount='swap')
        tunel_log(transfer)
    elif exchange == EXCHANGE.GATE:
        # unified account
        tunel_log("Gate is unified account, no need to transfer from spot to swap.")
    else:
        raise ValueError("Unsupported exchange for transfer to swap account.")


def transfer_tunel(from_exchange, to_exchange, amount):
    """
    Chuyển tiền từ tài khoản swap của sàn giao dịch này sang tài khoản swap của sàn giao dịch khác.

    :param from_exchange: Sàn giao dịch nguồn để thực hiện chuyển tiền.
    :param to_exchange: Sàn giao dịch đích để nhận tiền.
    :param amount: Số lượng tiền cần chuyển.
    """

    try:
        # wap to spot
        try_this(transfer_swap_to_spot, params={'exchange': from_exchange, 'amount': amount}, log_func=tunel_log, retries=5, delay=5)

        # Withdraw from spot to other exchange
        time.sleep(3)
        client_id = try_this(with_draw_from_spot, params={'f_exchange': from_exchange,'t_exchange':to_exchange,  'amount': amount}, log_func=tunel_log, retries=5, delay=5)

        # deposit to spot
        time.sleep(20)
        txid = try_this(get_withdrawal_txid, params={'exchange': from_exchange, 'order_id': client_id}, log_func=tunel_log, retries=30, delay=10)
        try_this(wait_for_desposit, params={'exchange': to_exchange, 'txid': txid}, log_func=tunel_log, retries=30, delay=10)

        # Transfer from spot to swap
        time.sleep(30)
        try_this(transfer_spot_to_swap, params={'exchange': to_exchange, 'amount': amount}, log_func=tunel_log, retries=5, delay=5)
        write_transfer_status(True, amount=amount, from_exchange=from_exchange.name.lower(), to_exchange=to_exchange.name.lower())
    except Exception as e:
        tunel_log(f"Transfer failed, {e}")
        write_transfer_status(False, amount=amount, from_exchange=from_exchange.name.lower(), to_exchange=to_exchange.name.lower())
        raise

def write_transfer_status(bOk, amount=None, from_exchange=None, to_exchange=None):
    # Ghi legacy file text
    with open(transfer_done_file, 'w+', encoding='utf-8') as f:
        if bOk:
            f.write('OK\n')
        else:
            f.write('ERROR\n')
    # Ghi file JSON trạng thái (atomic) để container khác đọc
    try:
        tmp_path = transfer_status_json_file + '.tmp'
        payload = {
            'status': 'OK' if bOk else 'ERROR',
            'amount': float(amount) if amount is not None else None,
            'from': from_exchange,
            'to': to_exchange,
            'finished_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'duration_sec': round(time.time() - start_time, 2)
        }
        with open(tmp_path, 'w', encoding='utf-8') as jf:
            json.dump(payload, jf, ensure_ascii=False)
        os.replace(tmp_path, transfer_status_json_file)
    except Exception as e:
        tunel_log(f'Cannot write transfer_status.json at done stage: {e}')

if __name__ == '__main__':

    if len(sys.argv) < 3:
        print("Usage: python Transfer.py <from_exchange> <to_exchange> <amount>")
        sys.exit(1)
    f_exchange = sys.argv[1]
    if f_exchange == 'binance':
        from_exchange = EXCHANGE.BINANCE
    elif f_exchange == 'bitget':
        from_exchange = EXCHANGE.BITGET
    elif f_exchange == 'gate':
        from_exchange = EXCHANGE.GATE
    elif f_exchange == 'bitget_sub':
        from_exchange = EXCHANGE.BITGET_SUB
    else:
        raise ValueError("Unsupported exchange. Use 'binance' or 'bitget'.")

    t_exchange = sys.argv[2]
    if t_exchange == 'binance':
        to_exchange = EXCHANGE.BINANCE
    elif t_exchange == 'bitget':
        to_exchange = EXCHANGE.BITGET
    elif t_exchange == 'gate':
        to_exchange = EXCHANGE.GATE
    elif t_exchange == 'bitget_sub':
        to_exchange = EXCHANGE.BITGET_SUB
    else:
        raise ValueError("Unsupported exchange. Use 'binance' or 'bitget'.")
    transfer_config = TransferConfig(from_exchange=from_exchange, to_exchange=to_exchange)
    amount = float(sys.argv[3])
    transfer_tunel(from_exchange, to_exchange, amount)
