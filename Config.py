import json
import sys

import boto3
from Core.Define import EXCHANGE
from Core.Tool import check_config_empty_by_error


def _load_exchange_config_from_secrets():
    """
    Try to load exchange credentials from AWS Secrets Manager.
    Expected secret payload is a JSON string compatible with legacy exchange.json structure,
    e.g. { "bitget": {"api_key": "...", "api_secret": "...", "password": "..."}, "gate": { ... } }

    Configuration:
    - AWS_SECRET_NAME: Name/ARN of the secret to fetch
    - AWS_REGION: Optional AWS region (if omitted, boto3 default resolution is used)
    """
    try:
        client = boto3.client('secretsmanager', region_name="ap-southeast-1")
        resp = client.get_secret_value(SecretId='exchange_key')
        secret_str = resp.get('SecretString')
        if not secret_str:
            print("AWS Secrets Manager returned no SecretString; fallback to exchange.json")
            return None
        data = json.loads(secret_str)
        print(f"Loaded exchange config from AWS Secrets Manager: exchange_key")
        return data
    except Exception as e:
        print(f"Failed to load secrets from AWS Secrets Manager: {e}. Fallback to exchange.json")
        return None


def get_credentials(exchange1: EXCHANGE, exchange2: EXCHANGE):
    """
    Load credentials for the specified exchanges and return them without storing globally.

    Returns a dict structure:
    {
      'binance': {'api_key': str, 'api_secret': str},
      'bitget': {'api_key': str, 'api_secret': str, 'password': str},
      'bitget_sub': {'api_key': str, 'api_secret': str, 'password': str},
      'gate': {'api_key': str, 'api_secret': str}
    }

    Only the requested exchanges (exchange1/exchange2) are validated for emptiness.
    Others are returned as empty strings to preserve previous behavior.
    """
    print(f"Loading configuration for exchanges: {exchange1}, {exchange2}")

    data = _load_exchange_config_from_secrets()
    if data is None:
        sys.exit(1)

    # Prepare default empty credentials
    creds = {
        'binance': {'api_key': '', 'api_secret': ''},
        'bitget': {'api_key': '', 'api_secret': '', 'password': ''},
        'bitget_sub': {'api_key': '', 'api_secret': '', 'password': ''},
        'gate': {'api_key': '', 'api_secret': ''},
    }

    # Helper to fill and validate
    def _fill_and_validate(name: str, required_keys):
        exchange_data = data.get(name, {})
        for k in creds[name].keys():
            creds[name][k] = exchange_data.get(k, '')
        if name.upper() == 'BINANCE':
            ex_enum = EXCHANGE.BINANCE
        elif name.upper() == 'BITGET':
            ex_enum = EXCHANGE.BITGET
        elif name.upper() == 'BITGET_SUB':
            ex_enum = EXCHANGE.BITGET_SUB
        elif name.upper() == 'GATE':
            ex_enum = EXCHANGE.GATE
        else:
            ex_enum = None
        if ex_enum is not None and (exchange1 == ex_enum or exchange2 == ex_enum):
            check_config_empty_by_error([creds[name].get(k, '') for k in required_keys])

    _fill_and_validate('bitget', ['api_key', 'api_secret', 'password'])
    _fill_and_validate('bitget_sub', ['api_key', 'api_secret', 'password'])
    _fill_and_validate('binance', ['api_key', 'api_secret'])
    _fill_and_validate('gate', ['api_key', 'api_secret'])

    return creds


# Backwards-compat wrapper if other modules still import load_config
# It returns the same dict as get_credentials for compatibility.
# Prefer calling get_credentials directly.

def load_config(exchange1: EXCHANGE, exchange2: EXCHANGE):
    return get_credentials(exchange1, exchange2)
