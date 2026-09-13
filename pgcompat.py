"""SQLite-like compatibility wrapper backed by PostgreSQL.
Activated only when sitecustomize.py sees DATABASE_URL.
"""
import os, re
import psycopg
from psycopg.rows import dict_row

Row = dict

def _sql(sql: str) -> str:
    s = sql
    s = re.sub(r'\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b', 'BIGSERIAL PRIMARY KEY', s, flags=re.I)
    s = s.replace('?', '%s')
    return s

class Cursor:
    def __init__(self, cur):
        self._cur = cur
    def execute(self, sql, params=()):
        self._cur.execute(_sql(sql), params or ())
        return self
    def fetchone(self):
        return self._cur.fetchone()
    def fetchall(self):
        return self._cur.fetchall()
    @property
    def rowcount(self):
        return self._cur.rowcount

class Connection:
    def __init__(self):
        url = os.environ['DATABASE_URL']
        self._conn = psycopg.connect(url, row_factory=dict_row)
        self.row_factory = Row
    def execute(self, sql, params=()):
        cur = self._conn.cursor()
        cur.execute(_sql(sql), params or ())
        return Cursor(cur)
    def commit(self):
        self._conn.commit()
    def rollback(self):
        self._conn.rollback()
    def close(self):
        self._conn.close()
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()
        return False

def connect(_ignored=None, *args, **kwargs):
    return Connection()
