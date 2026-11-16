"""Single-host transactional quotas and exact-response cache."""
import os
import json
import sqlite3
import time
from pathlib import Path
from src.build_data import ROOT
from src.storage import Database


class GuardrailError(ValueError):
    pass


def admission(question):
    import re
    patterns = [r'ignore.{0,30}(instructions|rules|prompt)',r'(reveal|show|print).{0,30}(api.key|secret|system.prompt)',
                r'\b(drop|delete|insert|update)\s+(table|from|into)\b',r'\b(next year|forecast|predict tomorrow)\b',
                r'(pretend|fabricate|make up).{0,30}(number|rate|answer)']
    if any(re.search(p,question,re.I) for p in patterns):
        raise GuardrailError('This request includes unsupported forecasting, instruction overrides or data manipulation. Ask a factual portfolio aggregation.')


def connect():
    path=Path(os.getenv('QA_DB_PATH',str(ROOT/'data/qa_controls.sqlite3')))
    path.parent.mkdir(parents=True,exist_ok=True)
    db=Database(path)
    db.execute('CREATE TABLE IF NOT EXISTS calls (created REAL, actor TEXT, tokens INTEGER)')
    db.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, created REAL, response TEXT)')
    return db


def cached(key):
    with connect() as db:
        row=db.execute('SELECT response FROM cache WHERE key=? AND created>?',(key,time.time()-3600)).fetchone()
    return json.loads(row[0]) if row else None


def reserve(actor):
    now=time.time()
    # Conservative reservation, not a dollar-price estimate. Count failures too.
    tokens=20000
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        day=int(now//86400)*86400
        count,total=db.execute('SELECT COUNT(*),COALESCE(SUM(tokens),0) FROM calls WHERE created>=?',(day,)).fetchone()
        minute=db.execute('SELECT COUNT(*) FROM calls WHERE created>?',(now-60,)).fetchone()[0]
        personal=db.execute('SELECT COUNT(*) FROM calls WHERE created>? AND actor=?',(now-60,actor)).fetchone()[0]
        if personal>=int(os.getenv('QA_SESSION_PER_MINUTE','5')) or minute>=int(os.getenv('QA_GLOBAL_PER_MINUTE','15')):
            raise GuardrailError('Request limit reached. Wait one minute before trying again.')
        if count>=int(os.getenv('QA_DAILY_REQUESTS','100')) or total+tokens>int(os.getenv('QA_DAILY_TOKEN_BUDGET','2000000')):
            raise GuardrailError('Daily AI request/token budget reached. Try again after the UTC day resets.')
        db.execute('INSERT INTO calls VALUES (?,?,?)',(now,actor,tokens))


def store(key,response):
    with connect() as db:
        db.execute('DELETE FROM cache WHERE created<?',(time.time()-3600,))
        db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)',(key,time.time(),json.dumps(response)))
