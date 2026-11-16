"""SQLite locally, PostgreSQL when DATABASE_URL is configured."""
import os
import sqlite3
from pathlib import Path


class Database:
    def __init__(self,path):
        self.postgres=bool(os.getenv('DATABASE_URL'))
        if self.postgres:
            import psycopg
            self.raw=psycopg.connect(os.environ['DATABASE_URL'],connect_timeout=15,sslmode='require')
        else:
            path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
            self.raw=sqlite3.connect(path,timeout=15)

    def execute(self,sql,params=()):
        if self.postgres:
            if sql=='BEGIN IMMEDIATE':
                return self.raw.execute('SELECT pg_advisory_xact_lock(719284621)')
            sql=sql.replace('id INTEGER PRIMARY KEY','id BIGSERIAL PRIMARY KEY')
            sql=sql.replace('created REAL','created DOUBLE PRECISION')
            sql=sql.replace('INSERT OR REPLACE INTO cache VALUES (?,?,?)',
                'INSERT INTO cache VALUES (?,?,?) ON CONFLICT (key) DO UPDATE SET created=EXCLUDED.created, response=EXCLUDED.response')
            sql=sql.replace('?','%s')
        return self.raw.execute(sql,params)

    def __enter__(self):
        return self

    def __exit__(self,kind,value,tb):
        try:
            self.raw.rollback() if kind else self.raw.commit()
        finally:
            self.raw.close()
