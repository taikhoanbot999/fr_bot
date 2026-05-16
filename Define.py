import os
import sys
from enum import Enum
from Core.Define import convert_exchange_name_to_exchange

class SERVICE_NAME(Enum):
    """
    Enum for service names.
    """
    ASSET_CONTROL = "asset_control"
    TP_SL_CONTROL = "tp_sl_control"
    ADL_CONTROL = "adl_control"

NULL = None
exchange1 = NULL
exchange2 = NULL

print(f"argv: {sys.argv}")

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_default_root = _REPO_ROOT if os.name == "nt" else "/home/ubuntu/fr_bot"
_deploy_root = os.path.abspath(os.environ.get("FR_BOT_ROOT", _default_root))
root_path = _deploy_root + os.sep


def _resolve_code_dir(deploy_root: str) -> str:
    """Linux/Docker: deploy_root/code/...  |  Windows dev (flat clone): deploy_root/_settings/..."""
    nested_cfg = os.path.join(deploy_root, "code", "_settings", "config.txt")
    flat_cfg = os.path.join(deploy_root, "_settings", "config.txt")
    if os.path.isfile(nested_cfg):
        return os.path.join(deploy_root, "code")
    if os.path.isfile(flat_cfg):
        return deploy_root
    raise FileNotFoundError(
        f"Settings not found. Expected {nested_cfg} or {flat_cfg}"
    )


code_dir = _resolve_code_dir(_deploy_root)
settings_dir = os.path.join(code_dir, "_settings")

setting_file = os.path.join(settings_dir, "config.txt")
if not os.path.exists(setting_file):
    raise FileNotFoundError(f"Setting file {setting_file} does not exist.")

with open(setting_file, 'r', encoding='utf-8') as f:
    settings = f.read().strip().splitlines()
    exchange1 = settings[0]
    exchange2 = settings[1]
    if exchange1 not in ['binance', 'bitget', 'bitget_sub', 'gate']:
        raise ValueError(f"Invalid exchange1: {exchange1}. Must be one of ['binance', 'bitget', 'bitget_sub', 'gate']")
    if exchange2 not in ['binance', 'bitget', 'bitget_sub', 'gate']:
        raise ValueError(f"Invalid exchange2: {exchange2}. Must be one of ['binance', 'bitget', 'bitget_sub', 'gate']")

    exchange1 = convert_exchange_name_to_exchange(exchange1)
    exchange2 = convert_exchange_name_to_exchange(exchange2)

    ini_path = settings[2]


log_path = os.path.join(root_path, "logs")
tunel_log_path = os.path.join(log_path, "tunel")
asset_log_path = os.path.join(log_path, "asset")
adl_log_path = os.path.join(log_path, "adl.txt")
tp_sl_log_path = os.path.join(log_path, "tp_sl.txt")

transfer_done_file = os.path.join(log_path, "transfer_done.txt")
# File JSON trạng thái transfer mới (atomic + dễ parse giữa container)
transfer_status_json_file = os.path.join(log_path, "transfer_status.json")

transfer_info_path = os.path.join(settings_dir, ini_path, "transfer.json")
balance_info_path = os.path.join(settings_dir, ini_path, "balance.json")
tp_sl_info_path = os.path.join(settings_dir, ini_path, "tp_sl.json")
discord_config_path = os.path.join(settings_dir, ini_path, "config.json")

server_config_path = os.path.join(settings_dir, "server.json")

shared_log_path = os.path.join(log_path, "shared.log")
discord_simple_log_path = os.path.join(log_path, "discord_simple.log")
