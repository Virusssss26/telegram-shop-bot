import sqlite3
from contextlib import closing
from typing import Any, Iterable


class Database:
    def __init__(self, path: str):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init(self) -> None:
        with closing(self.connect()) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    price REAL NOT NULL,
                    photo_file_id TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS carts (
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (user_id, product_id),
                    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    comment TEXT NOT NULL DEFAULT '',
                    total REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    product_id INTEGER,
                    product_name TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            cur.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES ('contacts_text', 'Контакты пока не заполнены.')"
            )
            conn.commit()

    def fetchall(self, query: str, params: Iterable[Any] = ()):
        with closing(self.connect()) as conn:
            return conn.execute(query, params).fetchall()

    def fetchone(self, query: str, params: Iterable[Any] = ()):
        with closing(self.connect()) as conn:
            return conn.execute(query, params).fetchone()

    def execute(self, query: str, params: Iterable[Any] = ()) -> int:
        with closing(self.connect()) as conn:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.lastrowid

    def executemany(self, query: str, seq_of_params: Iterable[Iterable[Any]]) -> None:
        with closing(self.connect()) as conn:
            conn.executemany(query, seq_of_params)
            conn.commit()
