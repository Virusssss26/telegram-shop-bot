from __future__ import annotations

from typing import Optional

from db import Database


class CatalogService:
    def __init__(self, db: Database):
        self.db = db

    # categories
    def list_categories(self):
        return self.db.fetchall(
            "SELECT id, name FROM categories ORDER BY sort_order ASC, id ASC"
        )

    def get_category(self, category_id: int):
        return self.db.fetchone(
            "SELECT id, name FROM categories WHERE id = ?", (category_id,)
        )

    def add_category(self, name: str) -> int:
        max_row = self.db.fetchone("SELECT COALESCE(MAX(sort_order), 0) AS m FROM categories")
        sort_order = int(max_row["m"]) + 1 if max_row else 1
        return self.db.execute(
            "INSERT INTO categories (name, sort_order) VALUES (?, ?)",
            (name.strip(), sort_order),
        )

    def rename_category(self, category_id: int, name: str) -> None:
        self.db.execute(
            "UPDATE categories SET name = ? WHERE id = ?",
            (name.strip(), category_id),
        )

    def delete_category(self, category_id: int) -> None:
        self.db.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    # products
    def list_products(self, category_id: Optional[int] = None):
        if category_id is None:
            return self.db.fetchall(
                """
                SELECT p.id, p.category_id, c.name AS category_name, p.name, p.description,
                       p.price, p.photo_file_id, p.is_active
                FROM products p
                JOIN categories c ON c.id = p.category_id
                WHERE p.is_active = 1
                ORDER BY p.id DESC
                """
            )
        return self.db.fetchall(
            """
            SELECT p.id, p.category_id, c.name AS category_name, p.name, p.description,
                   p.price, p.photo_file_id, p.is_active
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE p.category_id = ? AND p.is_active = 1
            ORDER BY p.id DESC
            """,
            (category_id,),
        )

    def list_all_products_for_admin(self):
        return self.db.fetchall(
            """
            SELECT p.id, p.category_id, c.name AS category_name, p.name, p.description,
                   p.price, p.photo_file_id, p.is_active
            FROM products p
            JOIN categories c ON c.id = p.category_id
            ORDER BY p.id DESC
            """
        )

    def get_product(self, product_id: int):
        return self.db.fetchone(
            """
            SELECT p.id, p.category_id, c.name AS category_name, p.name, p.description,
                   p.price, p.photo_file_id, p.is_active
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE p.id = ?
            """,
            (product_id,),
        )

    def add_product(
        self,
        category_id: int,
        name: str,
        description: str,
        price: float,
        photo_file_id: str,
    ) -> int:
        return self.db.execute(
            """
            INSERT INTO products (category_id, name, description, price, photo_file_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (category_id, name.strip(), description.strip(), price, photo_file_id.strip()),
        )

    def update_product_name(self, product_id: int, name: str) -> None:
        self.db.execute("UPDATE products SET name = ? WHERE id = ?", (name.strip(), product_id))

    def update_product_description(self, product_id: int, description: str) -> None:
        self.db.execute(
            "UPDATE products SET description = ? WHERE id = ?",
            (description.strip(), product_id),
        )

    def update_product_price(self, product_id: int, price: float) -> None:
        self.db.execute("UPDATE products SET price = ? WHERE id = ?", (price, product_id))

    def update_product_photo(self, product_id: int, photo_file_id: str) -> None:
        self.db.execute(
            "UPDATE products SET photo_file_id = ? WHERE id = ?",
            (photo_file_id.strip(), product_id),
        )

    def update_product_category(self, product_id: int, category_id: int) -> None:
        self.db.execute(
            "UPDATE products SET category_id = ? WHERE id = ?",
            (category_id, product_id),
        )

    def delete_product(self, product_id: int) -> None:
        self.db.execute("DELETE FROM products WHERE id = ?", (product_id,))

    # cart
    def add_to_cart(self, user_id: int, product_id: int) -> None:
        existing = self.db.fetchone(
            "SELECT quantity FROM carts WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        if existing:
            self.db.execute(
                "UPDATE carts SET quantity = quantity + 1 WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            )
            return
        self.db.execute(
            "INSERT INTO carts (user_id, product_id, quantity) VALUES (?, ?, 1)",
            (user_id, product_id),
        )

    def change_cart_quantity(self, user_id: int, product_id: int, delta: int) -> None:
        self.db.execute(
            "UPDATE carts SET quantity = quantity + ? WHERE user_id = ? AND product_id = ?",
            (delta, user_id, product_id),
        )
        self.db.execute(
            "DELETE FROM carts WHERE user_id = ? AND product_id = ? AND quantity <= 0",
            (user_id, product_id),
        )

    def remove_from_cart(self, user_id: int, product_id: int) -> None:
        self.db.execute(
            "DELETE FROM carts WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )

    def clear_cart(self, user_id: int) -> None:
        self.db.execute("DELETE FROM carts WHERE user_id = ?", (user_id,))

    def get_cart(self, user_id: int):
        return self.db.fetchall(
            """
            SELECT p.id, p.name, p.price, p.photo_file_id, c.quantity
            FROM carts c
            JOIN products p ON p.id = c.product_id
            WHERE c.user_id = ?
            ORDER BY p.id DESC
            """,
            (user_id,),
        )

    def cart_total(self, user_id: int) -> float:
        row = self.db.fetchone(
            """
            SELECT COALESCE(SUM(p.price * c.quantity), 0) AS total
            FROM carts c
            JOIN products p ON p.id = c.product_id
            WHERE c.user_id = ?
            """,
            (user_id,),
        )
        return float(row["total"]) if row else 0.0

    # orders
    def create_order(self, user_id: int, phone: str, address: str, comment: str) -> int:
        def create(conn):
            items = conn.execute(
                """
                SELECT p.id, p.name, p.price, p.photo_file_id, c.quantity
                FROM carts c
                JOIN products p ON p.id = c.product_id
                WHERE c.user_id = ?
                ORDER BY p.id DESC
                """,
                (user_id,),
            ).fetchall()
            if not items:
                raise ValueError("Cart is empty")

            total_row = conn.execute(
                """
                SELECT COALESCE(SUM(p.price * c.quantity), 0) AS total
                FROM carts c
                JOIN products p ON p.id = c.product_id
                WHERE c.user_id = ?
                """,
                (user_id,),
            ).fetchone()
            total = float(total_row["total"]) if total_row else 0.0

            cur = conn.execute(
                """
                INSERT INTO orders (user_id, phone, address, comment, total)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, phone.strip(), address.strip(), comment.strip(), total),
            )
            order_id = cur.lastrowid

            conn.executemany(
                """
                INSERT INTO order_items (order_id, product_id, product_name, price, quantity)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (order_id, int(row["id"]), str(row["name"]), float(row["price"]), int(row["quantity"]))
                    for row in items
                ],
            )
            conn.execute("DELETE FROM carts WHERE user_id = ?", (user_id,))
            return int(order_id)

        return self.db.transaction(create)

    def list_orders(self):
        return self.db.fetchall(
            "SELECT * FROM orders ORDER BY id DESC"
        )

    def get_order(self, order_id: int):
        return self.db.fetchone("SELECT * FROM orders WHERE id = ?", (order_id,))

    def get_order_items(self, order_id: int):
        return self.db.fetchall(
            "SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC",
            (order_id,),
        )

    def update_order_status(self, order_id: int, status: str) -> None:
        self.db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))

    # settings
    def get_contacts_text(self) -> str:
        row = self.db.fetchone("SELECT value FROM settings WHERE key = 'contacts_text'")
        return str(row["value"]) if row else "Контакты пока не заполнены."

    def set_contacts_text(self, text: str) -> None:
        self.db.execute(
            "UPDATE settings SET value = ? WHERE key = 'contacts_text'",
            (text.strip(),),
        )
