import json
import bcrypt
from pathlib import Path

users_file = Path('data/users.json')

with open(users_file, 'r', encoding='utf-8') as f:
    users = json.load(f)

for phone, data in users.items():
    plain_pin = data.get('pin')
    if plain_pin and not plain_pin.startswith('$2b$'):
        # bcrypt requires bytes
        hashed = bcrypt.hashpw(plain_pin.encode('utf-8'), bcrypt.gensalt())
        data['pin'] = hashed.decode('utf-8')

with open(users_file, 'w', encoding='utf-8') as f:
    json.dump(users, f, indent=2)

print("Hashed pins successfully with pure bcrypt!")
