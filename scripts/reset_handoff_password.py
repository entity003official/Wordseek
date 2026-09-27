"""Reset only an explicitly selected account in a marked handoff COPY."""
import getpass
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if not (root / 'HANDOFF_COPY.json').is_file():
    raise SystemExit('Refused: this is not a marked handoff copy.')
sys.path.insert(0, str(root / '.venv' / 'Lib' / 'site-packages'))
from argon2 import PasswordHasher

database = root / 'backend/data/beyond_words_v1.db'
connection = sqlite3.connect(database)
for (email,) in connection.execute('select email from users'):
    print(email)
email = input('Account email in this COPY: ').strip().casefold()
if connection.execute('select id from users where email=?', (email,)).fetchone() is None:
    raise SystemExit('Account not found; no changes made.')
password = getpass.getpass('New password (12+ characters): ')
if len(password) < 12 or password != getpass.getpass('Repeat password: '):
    raise SystemExit('Invalid password or mismatch; no changes made.')
backup = root / 'outputs' / ('before-copy-password-reset-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.db')
with sqlite3.connect(backup) as target:
    connection.backup(target)
connection.execute('update users set password_hash=? where email=?', (PasswordHasher().hash(password), email))
connection.commit()
connection.close()
print('Password changed only in this handoff copy. Existing source files were not accessed.')
