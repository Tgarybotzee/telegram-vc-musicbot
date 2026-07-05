import aiosqlite
from config import DB_PATH, logger

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                role TEXT DEFAULT 'user',
                credits INTEGER DEFAULT 0,
                is_banned BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS accounts (
                phone TEXT PRIMARY KEY,
                session_string TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                assigned_to INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(assigned_to) REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );
        """)
        await db.commit()

async def register_user(user_id: int, username: str, role: str = 'user'):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, role) VALUES (?, ?, ?)",
            (user_id, username, role)
        )
        await db.commit()

async def get_user_profile(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {}

async def save_telethon_session(phone: str, session_string: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO accounts (phone, session_string, status) VALUES (?, ?, 'active')",
            (phone, session_string)
        )
        await db.commit()

async def get_all_accounts() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT phone, status, assigned_to FROM accounts") as cursor:
            return [dict(row) async for row in cursor]

async def get_user_accounts(user_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT phone, status FROM accounts WHERE assigned_to = ?", (user_id,)) as cursor:
            return [dict(row) async for row in cursor]

async def get_account_session(phone: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT session_string FROM accounts WHERE phone = ?", (phone,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def get_all_sessions_export() -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT phone, session_string FROM accounts") as cursor:
            rows = await cursor.fetchall()
            if not rows: return "No accounts found."
            return "\n".join([f"{row[0]},{row[1]}" for row in rows])

async def get_all_account_sessions() -> list:
    """Returns a list of tuples containing (phone, session_string) for all accounts."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT phone, session_string FROM accounts") as cursor:
            return await cursor.fetchall()

async def assign_account_to_user(admin_id: int, user_id: int, phone: str) -> tuple[bool, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("BEGIN EXCLUSIVE")
            async with db.execute("SELECT credits, is_banned FROM users WHERE user_id = ?", (user_id,)) as cur:
                user = await cur.fetchone()
                if not user: return False, "User not found."
                if user[1]: return False, "User is banned."
                if user[0] < 1: return False, "Insufficient credits."

            async with db.execute("SELECT status, assigned_to FROM accounts WHERE phone = ?", (phone,)) as cur:
                acc = await cur.fetchone()
                if not acc: return False, "Account not found."
                if acc[0] != 'active' or acc[1] is not None: return False, "Account is unavailable."

            await db.execute("UPDATE users SET credits = credits - 1 WHERE user_id = ?", (user_id,))
            await db.execute("UPDATE accounts SET assigned_to = ? WHERE phone = ?", (user_id, phone))
            await db.execute(
                "INSERT INTO transactions (user_id, amount, description) VALUES (?, ?, ?)",
                (user_id, -1, f"Assigned account {phone}")
            )
            await db.commit()
            return True, f"Account {phone} assigned to user {user_id}."
        except Exception as e:
            await db.rollback()
            return False, "Database error occurred."