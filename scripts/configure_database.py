"""Privately configure Supabase PostgreSQL in ignored Streamlit secrets."""
import getpass
import json
from pathlib import Path
from urllib.parse import quote
import tomllib
import re

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'.streamlit/secrets.toml'
password=getpass.getpass('Supabase database password (hidden): ')
if not password:
    raise SystemExit('Password cannot be empty; nothing saved.')
url=('postgresql://postgres.xxdwrakctfxeaggqytwb:'+quote(password,safe='')+
     '@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require')
text=path.read_text() if path.exists() else ''
tomllib.loads(text)  # Refuse to alter a malformed existing secrets file.
line='DATABASE_URL = '+json.dumps(url)
if re.search(r'^\s*DATABASE_URL\s*=',text,re.M):
    text=re.sub(r'^\s*DATABASE_URL\s*=.*$',lambda match:line,text,flags=re.M)
else:
    # Place before any TOML tables so the secret stays at the root.
    text=line+'\n'+text
tomllib.loads(text)
path.parent.mkdir(exist_ok=True)
path.write_text(text)
path.chmod(0o600)
print('DATABASE_URL saved privately. Existing secrets preserved. No password printed.')
