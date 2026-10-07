"""Small SQL adapter: SQLite locally, psycopg/PostgreSQL when DATABASE_URL is set."""
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

WRITE_LOCK = 728193401
IDENTITY_TABLES = {'users', 'items', 'locations', 'adjustments', 'returns', 'return_events', 'movements'}


class Record(dict):
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def record_factory(cursor):
    columns = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: Record(zip(columns, values))


class Cursor:
    def __init__(self, cursor, identity=False):
        self.cursor = cursor
        self.rowcount = cursor.rowcount
        self.lastrowid = cursor.fetchone()['id'] if identity else None

    def fetchone(self):
        return self.cursor.fetchone()

    def __iter__(self):
        return iter(self.cursor)


class PostgresConnection:
    def __init__(self, connection):
        self.raw = connection

    def execute(self, sql, parameters=()):
        if sql.strip().upper() == 'BEGIN IMMEDIATE':
            # Preserve SQLite's serialized read/check/write semantics across workers.
            return Cursor(self.raw.execute('SELECT pg_advisory_xact_lock(%s)', (WRITE_LOCK,)))
        match = re.match(r'\s*INSERT\s+INTO\s+(\w+)', sql, re.I)
        identity = bool(match and match[1].lower() in IDENTITY_TABLES)
        if identity:
            sql += ' RETURNING id'
        return Cursor(self.raw.execute(sql.replace('?', '%s'), parameters), identity)

    def executescript(self, script):
        for statement in script.split(';'):
            if statement.strip():
                self.raw.execute(statement)


def is_postgres(target):
    return str(target).startswith(('postgres://', 'postgresql://'))


@contextmanager
def connection(target):
    if is_postgres(target):
        import psycopg
        with psycopg.connect(str(target), row_factory=record_factory, connect_timeout=15,
                             prepare_threshold=None) as raw:
            try:
                yield PostgresConnection(raw)
            except psycopg.IntegrityError as exc:
                raise sqlite3.IntegrityError('Duplicate entry or invalid reference') from exc
    else:
        con = sqlite3.connect(str(target), timeout=10)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def initialize(target):
    filename = 'schema-postgres.sql' if is_postgres(target) else 'schema.sql'
    with connection(target) as con:
        con.execute('BEGIN IMMEDIATE')
        con.executescript(Path(__file__).with_name(filename).read_text())
