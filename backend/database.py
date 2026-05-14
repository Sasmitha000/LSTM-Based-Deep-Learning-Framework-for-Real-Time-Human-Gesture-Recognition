import os
import sqlite3

DATABASE_URL = os.environ.get('DATABASE_URL', None)

def get_db():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        conn = sqlite3.connect('signbridge.db')
        conn.row_factory = sqlite3.Row
        return conn

def execute(conn, query, params=()):
    if DATABASE_URL:
        query = query.replace('?', '%s')
        query = query.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    if DATABASE_URL:
        cursor.execute(query_adapt('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_verified INTEGER DEFAULT 1,
                verification_token TEXT,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        '''))

        cursor.execute(query_adapt('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                purpose TEXT,
                usage_count INTEGER DEFAULT 0,
                last_used TEXT,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        '''))

        cursor.execute(query_adapt('''
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        '''))

        cursor.execute(query_adapt('''
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'admin',
                permissions TEXT DEFAULT 'overview,model,analytics,environment,contributions,users',
                created_at TEXT NOT NULL,
                created_by TEXT DEFAULT 'superadmin',
                last_login TEXT,
                is_active INTEGER DEFAULT 1
            )
        '''))

        cursor.execute(query_adapt('''
            CREATE TABLE IF NOT EXISTS admin_sessions (
                id SERIAL PRIMARY KEY,
                admin_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (admin_id) REFERENCES admins(id)
            )
        '''))

    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_verified INTEGER DEFAULT 1,
                verification_token TEXT,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                purpose TEXT,
                usage_count INTEGER DEFAULT 0,
                last_used TEXT,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'admin',
                permissions TEXT DEFAULT 'overview,model,analytics,environment,contributions,users',
                created_at TEXT NOT NULL,
                created_by TEXT DEFAULT 'superadmin',
                last_login TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (admin_id) REFERENCES admins(id)
            )
        ''')

    conn.commit()
    conn.close()
    print("Database initialized!")

def query_adapt(query):
    if DATABASE_URL:
        query = query.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
        query = query.replace('?', '%s')
    return query

def dict_row(cursor, row):
    if DATABASE_URL:
        if cursor.description:
            return {desc[0]: val for desc, val in zip(cursor.description, row)}
        return {}
    return dict(row)

def fetchone_dict(cursor):
    if DATABASE_URL:
        row = cursor.fetchone()
        if row and cursor.description:
            return {desc[0]: val for desc, val in zip(cursor.description, row)}
        return None
    return cursor.fetchone()

def fetchall_dict(cursor):
    if DATABASE_URL:
        rows = cursor.fetchall()
        if rows and cursor.description:
            return [{desc[0]: val for desc, val in zip(cursor.description, row)} for row in rows]
        return []
    return [dict(row) for row in cursor.fetchall()]

def adapt_query(query):
    if DATABASE_URL:
        query = query.replace('?', '%s')
    return query

if __name__ == '__main__':
    init_db()
