"""Check TLS connectivity and storage schema without printing credentials."""
import os
import sys
import tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
secrets=tomllib.loads((ROOT/'.streamlit/secrets.toml').read_text())
os.environ['DATABASE_URL']=secrets['DATABASE_URL']
from src.reviews import read_reviews
from src.qa_controls import connect
try:
    rows=read_reviews()
    with connect() as db:
        db.execute('SELECT 1').fetchone()
    print('PASS: PostgreSQL connected; review, quota and cache tables ready.')
    print('Existing review records:',len(rows))
except Exception as exc:
    print('Database check failed:',type(exc).__name__)
    print('Check project availability, database password and Session pooler settings. Credentials were not printed.')
    raise SystemExit(1)
