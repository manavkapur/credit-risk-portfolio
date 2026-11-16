"""Transactional append-only SQLite review history. Configure durable storage on hosting."""
import os
import sqlite3
from src.storage import Database
from datetime import datetime, timezone
from pathlib import Path
from src.build_data import ROOT


def connect(path=None):
    path = Path(path or os.getenv('REVIEW_DB_PATH',str(ROOT/'data/reviews.sqlite3')))
    path.parent.mkdir(parents=True,exist_ok=True)
    db = Database(path)
    db.execute('CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY, account_id TEXT NOT NULL, anomaly_version TEXT NOT NULL, decision TEXT NOT NULL, note TEXT NOT NULL, reviewer TEXT NOT NULL, created_at TEXT NOT NULL)')
    return db


def save_review(account_id, anomaly_version, decision, note='', reviewer='Demo analyst', path=None):
    if decision not in {'confirm','dismiss'}:
        raise ValueError('Decision must be confirm or dismiss')
    if not account_id or not anomaly_version or not reviewer:
        raise ValueError('Account, anomaly version and reviewer required')
    with connect(path) as db:
        db.execute('INSERT INTO reviews(account_id,anomaly_version,decision,note,reviewer,created_at) VALUES (?,?,?,?,?,?)',
            (account_id,anomaly_version,decision,note,reviewer,datetime.now(timezone.utc).isoformat()))


def read_reviews(path=None):
    import pandas as pd
    with connect(path) as db:
        cursor=db.execute('SELECT * FROM reviews ORDER BY id DESC')
        return pd.DataFrame(cursor.fetchall(),columns=[column[0] for column in cursor.description])
