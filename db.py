import time
import aiosqlite

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance REAL DEFAULT 0,
    last_seen_balance REAL DEFAULT 0,
    reputation REAL DEFAULT 0,
    has_vacuum INTEGER DEFAULT 0,
    has_polisher INTEGER DEFAULT 0,
    has_steamer INTEGER DEFAULT 0,
    has_ceramic INTEGER DEFAULT 0,
    washes_today INTEGER DEFAULT 0,
    last_daily_tick TEXT DEFAULT '',
    created_at REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bays (
    bay_id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,
    status TEXT DEFAULT 'free',      -- free / busy / broken
    broken_until REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS workers (
    worker_id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,
    level TEXT,
    name TEXT,
    status TEXT DEFAULT 'idle',      -- idle / working
    busy_until REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,
    service_type TEXT,
    is_vip INTEGER DEFAULT 0,
    created_at REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,
    worker_id INTEGER,
    bay_id INTEGER,
    service_type TEXT,
    started_at REAL,
    finish_at REAL,
    payout REAL,
    resolved INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pending_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,
    event_type TEXT,
    payload TEXT,
    created_at REAL,
    expires_at REAL,
    resolved INTEGER DEFAULT 0
);
"""


async def init_db():
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def get_conn():
    conn = await aiosqlite.connect(config.DB_PATH)
    conn.row_factory = aiosqlite.Row
    return conn


async def get_user(db, user_id: int):
    cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return await cur.fetchone()


async def create_user_if_not_exists(db, user_id: int, username: str):
    user = await get_user(db, user_id)
    if user:
        return False
    now = time.time()
    await db.execute(
        "INSERT INTO users (user_id, username, balance, last_seen_balance, reputation, created_at, last_daily_tick) "
        "VALUES (?, ?, ?, ?, 0, ?, ?)",
        (user_id, username, config.STARTING_BALANCE, config.STARTING_BALANCE, now, time.strftime("%Y-%m-%d")),
    )
    # стартовый бокс
    await db.execute("INSERT INTO bays (owner_id, status) VALUES (?, 'free')", (user_id,))
    # стартовый мойщик-новичок
    await db.execute(
        "INSERT INTO workers (owner_id, level, name, status) VALUES (?, 'novice', 'Стартовый мойщик', 'idle')",
        (user_id,),
    )
    await db.commit()
    return True


async def get_all_user_ids(db):
    cur = await db.execute("SELECT user_id FROM users")
    rows = await cur.fetchall()
    return [r["user_id"] for r in rows]


async def get_bays(db, owner_id: int):
    cur = await db.execute("SELECT * FROM bays WHERE owner_id=?", (owner_id,))
    return await cur.fetchall()


async def get_workers(db, owner_id: int):
    cur = await db.execute("SELECT * FROM workers WHERE owner_id=?", (owner_id,))
    return await cur.fetchall()


async def get_queue(db, owner_id: int):
    cur = await db.execute(
        "SELECT * FROM queue WHERE owner_id=? ORDER BY is_vip DESC, created_at ASC", (owner_id,)
    )
    return await cur.fetchall()


async def get_active_orders(db, owner_id: int):
    cur = await db.execute("SELECT * FROM orders WHERE owner_id=? AND resolved=0", (owner_id,))
    return await cur.fetchall()
