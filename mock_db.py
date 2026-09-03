import json
import asyncio
import os
from pathlib import Path

# A global lock to prevent race conditions during concurrent JSON reads/writes
db_lock = asyncio.Lock()

BASE_DIR = Path(__file__).parent
USERS_FILE = BASE_DIR / 'data' / 'users.json'
ACCOUNTS_FILE = BASE_DIR / 'data' / 'accounts.json'
TRANSACTIONS_FILE = BASE_DIR / 'data' / 'transactions.json'

def _load_json_sync(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def _save_json_sync(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

async def load_json(path):
    return _load_json_sync(path)

async def save_json(path, data):
    _save_json_sync(path, data)

async def get_user(phone: str):
    async with db_lock:
        users = await load_json(USERS_FILE)
        return users.get(phone)

async def get_account(acc_id: str):
    async with db_lock:
        accounts = await load_json(ACCOUNTS_FILE)
        return accounts.get(acc_id)