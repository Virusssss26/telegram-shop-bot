from __future__ import annotations
from typing import Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from services.catalog import CatalogService

ORDER_STATUS_LABELS = {
    "new": "🆕 Новый",
    "confirmed": "✅ Подтверждён",
    "done": "📦 Завершён",
    "cancelled": "❌ Отменён",
}


class TelegramShopBot:
    def __init__(self, token: str, admin_id: int, catalog: CatalogService):
        self.token = token
        self.admin_id = admin_id
        self.catalog = catalog

    # ---------- common UI ----------
    def is_admin(self, user_id: int) -> bool:
        return user_id == self.admin_id

    def main_keyboard(self, user_id: int) -> ReplyKeyboardMarkup:
        if self.is_admin(user_id):
            keyboard = [
                ["🛍 Каталог", "🛒 Корзина"],
                ["📂 Категории", "📦 Товары"],
                ["📬 Заказы", "🗃 Архив заказов"],
                ["ℹ️ Контакты"],
            ]
        else:
            keyboard = [
                ["🛍 Каталог", "🛒 Корзина"],
                ["ℹ️ Контакты"],
            ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def cancel_keyboard(self) -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup([["↩️ Отмена"]], resize_keyboard=True)

    async def send_main_menu(self, target, context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str = "Главное меню"):
        if hasattr(target, "reply_text"):
            await target.reply_text(text, reply_markup=self.main_keyboard(user_id))
        else:
            await context.bot.send_message(chat_id=target, text=text, reply_markup=self.main_keyboard(user_id))

    def categories_keyboard(self, admin: bool = False) -> InlineKeyboardMarkup:
        rows = []
        for cat in self.catalog.list_categories():
            if admin:
                rows.append([
                    InlineKeyboardButton(f"{cat['name']}", callback_data=f"admcatopen:{cat['id']}")
                ])
            else:
                rows.append([
                    InlineKeyboardButton(f"{cat['name']}", callback_data=f"cat:{cat['id']}")
                ])
        if admin:
            rows.append([InlineKeyboardButton("➕ Добавить категорию", callback_data="admcat:add")])
        rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="nav:main")])
        return InlineKeyboardMarkup(rows)

    def products_keyboard(self, category_id: int) -> InlineKeyboardMarkup:
        rows = []
        for product in self.catalog.list_products(category_id):
            rows.append([
                InlineKeyboardButton(
                    f"{product['name']} · {product['price']:.2f}",
                    callback_data=f"prodview:{product['id']}",
                ),
                InlineKeyboardButton("🛒", callback_data=f"prodadd:{product['id']}"),
            ])
        rows.append([InlineKeyboardButton("⬅️ К разделам", callback_data="catalog:back")])
        rows.append([InlineKeyboardButton("🛒 Корзина", callback_data="cart:open")])
        return InlineKeyboardMarkup(rows)

    def admin_products_keyboard(self) -> InlineKeyboardMarkup:
        rows = [[InlineKeyboardButton("➕ Добавить товар", callback_data="admprod:add")]]
        for product in self.catalog.list_all_products_for_admin()[:40]:
            rows.append([
                InlineKeyboardButton(
                    f"#{product['id']} · {product['name']} · {product['category_name']}",
                    callback_data=f"admprod:view:{product['id']}",
                )
            ])
        rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="nav:main")])
        return InlineKeyboardMarkup(rows)

    def cart_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        rows = []
        for item in self.catalog.get_cart(user_id):
            rows.append([
                InlineKeyboardButton(f"➖ {item['name']}", callback_data=f"cart:dec:{item['id']}"),
                InlineKeyboardButton(f"➕", callback_data=f"cart:inc:{item['id']}"),
                InlineKeyboardButton("🗑", callback_data=f"cart:rm:{item['id']}"),
            ])
        rows.append([InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout:start")])
        rows.append([InlineKeyboardButton("🏠 Главное меню", callback_data="nav:main")])
        return InlineKeyboardMarkup(rows)

    def admin_product_manage_keyboard(self, product_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Название", callback_data=f"admprod:editname:{product_id}")],
            [InlineKeyboardButton("📝 Описание", callback_data=f"admprod:editdesc:{product_id}")],
            [InlineKeyboardButton("💰 Цена", callback_data=f"admprod:editprice:{product_id}")],
            [InlineKeyboardButton("🖼 Фото", callback_data=f"admprod:editphoto:{product_id}")],
            [InlineKeyboardButton("📁 Сменить категорию", callback_data=f"admprod:movecat:{product_id}")],
            [InlineKeyboardButton("❌ Удалить товар", callback_data=f"admprod:delete:{product_id}")],
            [InlineKeyboardButton("⬅️ Назад к товарам", callback_data="admprod:list")],
        ])

    def product_preview_keyboard(self, save_callback: str, cancel_callback: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Сохранить", callback_data=save_callback),
                InlineKeyboardButton("↩️ Отмена", callback_data=cancel_callback),
            ]
        ])

    def admin_category_manage_keyboard(self, category_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Переименовать", callback_data=f"admcat:rename:{category_id}")],
            [InlineKeyboardButton("❌ Удалить", callback_data=f"admcat:delete:{category_id}")],
            [InlineKeyboardButton("⬅️ Назад к категориям", callback_data="admcat:list")],
        ])

    def order_keyboard(self, order_id: int, archived: bool = False) -> InlineKeyboardMarkup:
        rows = []
        if archived:
            rows.append([
                InlineKeyboardButton("📬 Активные заказы", callback_data="orders:list"),
                InlineKeyboardButton("⬅️ К архиву заказов", callback_data="orders:archive"),
            ])
            return InlineKeyboardMarkup(rows)

        rows.extend([
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"order:confirmed:{order_id}"),
                InlineKeyboardButton("📦 Завершить", callback_data=f"order:done:{order_id}"),
            ],
            [InlineKeyboardButton("❌ Отменить", callback_data=f"order:cancelled:{order_id}")],
            [
                InlineKeyboardButton("🗃 Архив заказов", callback_data="orders:archive"),
                InlineKeyboardButton("⬅️ К заказам", callback_data="orders:list"),
            ],
        ])
        return InlineKeyboardMarkup(rows)

    def orders_section_keyboard(self, archived: bool = False) -> InlineKeyboardMarkup:
        if archived:
            rows = [[InlineKeyboardButton("📬 Активные заказы", callback_data="orders:list")]]
        else:
            rows = [[InlineKeyboardButton("🗃 Архив заказов", callback_data="orders:archive")]]
        return InlineKeyboardMarkup(rows)

    # ---------- formatting ----------
    def format_product_card(self, product) -> str:
        return (
            f"<b>{product['name']}</b>\n"
            f"Цена: {product['price']:.2f}"
        )

    def format_product_full(self, product) -> str:
        return (
            f"<b>{product['name']}</b>\n"
            f"Категория: {product['category_name']}\n"
            f"Цена: {product['price']:.2f}\n\n"
            f"{product['description']}"
        )

    def format_product_compact(self, product) -> str:
        description = (product["description"] or "").strip()
        if description:
            short_description = description[:100] + ("..." if len(description) > 100 else "")
            return (
                f"<b>{product['name']}</b>\n"
                f"Цена: {product['price']:.2f}\n\n"
                f"{short_description}"
            )
        return (
            f"<b>{product['name']}</b>\n"
            f"Цена: {product['price']:.2f}"
        )

    def product_compact_keyboard(self, product) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Подробнее", callback_data=f"prodfull:{product['id']}"),
                InlineKeyboardButton("🛒 В корзину", callback_data=f"prodadd:{product['id']}"),
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data=f"cat:{product['category_id']}")],
        ])

    def product_detail_keyboard(self, product) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 В корзину", callback_data=f"prodadd:{product['id']}")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data=f"prodview:{product['id']}"),
                InlineKeyboardButton("🛒 Корзина", callback_data="cart:open"),
            ],
        ])

    async def show_product_message(self, query, context, product, text: str, keyboard: InlineKeyboardMarkup):
        if product["photo_file_id"]:
            async def send_photo():
                await context.bot.send_photo(
                    chat_id=query.message.chat.id,
                    photo=product["photo_file_id"],
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )

            if getattr(query.message, "photo", None):
                try:
                    await query.edit_message_media(
                        media=InputMediaPhoto(
                            media=product["photo_file_id"],
                            caption=text,
                            parse_mode="HTML",
                        ),
                    )
                    await query.edit_message_reply_markup(reply_markup=keyboard)
                except BadRequest as exc:
                    error_text = str(exc).lower()
                    if "message is not modified" in error_text:
                        await query.edit_message_reply_markup(reply_markup=keyboard)
                        return
                    if "message can't be edited" in error_text:
                        await send_photo()
                    else:
                        raise
            else:
                await send_photo()
            return

        await self.edit_or_send_message(
            query,
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    def build_product_preview(self, draft: dict, product=None) -> dict:
        if product:
            category_name = product["category_name"]
            name = draft.get("name", product["name"])
            description = draft.get("description", product["description"])
            price = float(draft.get("price", product["price"]))
            photo_file_id = draft.get("photo_file_id", product["photo_file_id"])
        else:
            category = self.catalog.get_category(int(draft["category_id"]))
            category_name = category["name"] if category else "Не указана"
            name = draft["name"]
            description = draft["description"]
            price = float(draft["price"])
            photo_file_id = draft["photo_file_id"]

        return {
            "name": name,
            "description": description,
            "price": price,
            "photo_file_id": photo_file_id,
            "category_name": category_name,
        }

    async def send_product_preview(
        self,
        message,
        product: dict,
        text: str,
        reply_markup: InlineKeyboardMarkup,
    ):
        preview_text = f"{text}\n\n{self.format_product_full(product)}"
        if product["photo_file_id"]:
            await message.reply_photo(
                photo=product["photo_file_id"],
                caption=preview_text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        else:
            await message.reply_text(
                preview_text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

    def format_cart_text(self, user_id: int) -> str:
        items = self.catalog.get_cart(user_id)
        if not items:
            return "🛒 Корзина пуста."
        lines = ["<b>🛒 Ваша корзина</b>"]
        for item in items:
            subtotal = float(item['price']) * int(item['quantity'])
            lines.append(f"• {item['name']} × {item['quantity']} = {subtotal:.2f}")
        lines.append("")
        lines.append(f"Итого: <b>{self.catalog.cart_total(user_id):.2f}</b>")
        return "\n".join(lines)

    async def edit_or_send_message(
        self,
        query,
        text: str,
        reply_markup=None,
        parse_mode: Optional[str] = None,
    ):
        try:
            if getattr(query.message, "photo", None):
                await query.edit_message_caption(
                    caption=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
            else:
                await query.edit_message_text(
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
        except BadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return
            await query.message.reply_text(
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )

    def format_order_text(self, order, items) -> str:
        lines = [
            f"<b>Заказ #{order['id']}</b>",
            f"Статус: {ORDER_STATUS_LABELS.get(order['status'], order['status'])}",
            f"Клиент: {order['customer_name'] or 'Не указано'} (ID: {order['user_id']})",
            f"Телефон: {order['phone']}",
            f"Адрес: {order['address']}",
            f"Комментарий: {order['comment'] or '—'}",
            f"Сумма: {order['total']:.2f}",
            f"Создан: {order['created_at']}",
            "",
            "<b>Состав заказа</b>",
        ]
        for item in items:
            lines.append(f"• {item['product_name']} × {item['quantity']} = {item['price'] * item['quantity']:.2f}")
        return "\n".join(lines)

    # ---------- state helpers ----------
    def set_state(self, context: ContextTypes.DEFAULT_TYPE, state: Optional[str], **kwargs):
        context.user_data["state"] = state
        if kwargs:
            draft = context.user_data.get("draft", {})
            draft.update(kwargs)
            context.user_data["draft"] = draft
        elif state is None:
            context.user_data.pop("draft", None)

    def clear_state(self, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.pop("state", None)
        context.user_data.pop("draft", None)

    def is_valid_phone(self, phone: str) -> bool:
        normalized = phone.strip()
        allowed_chars = set("0123456789+()- ")
        if not normalized or any(char not in allowed_chars for char in normalized):
            return False

        digits = "".join(char for char in normalized if char.isdigit())
        plus_count = normalized.count("+")
        if plus_count > 1:
            return False
        if plus_count == 1 and not normalized.startswith("+"):
            return False
        return 10 <= len(digits) <= 15

    def is_valid_name(self, name: str) -> bool:
        return bool(name.strip())

    def is_valid_address(self, address: str) -> bool:
        return bool(address.strip())

    # ---------- handlers ----------
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = "👋 Добро пожаловать. Используйте кнопки ниже." if not self.is_admin(update.effective_user.id) else "👋 Админ-панель готова."
        await update.message.reply_text(text, reply_markup=self.main_keyboard(update.effective_user.id))

    async def text_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = (update.message.text or "").strip()
        state = context.user_data.get("state")
        draft = context.user_data.get("draft", {})

        if text == "↩️ Отмена":
            self.clear_state(context)
            await self.send_main_menu(update.message, context, user_id, "Действие отменено.")
            return
        
        # stateful flows first
        if state == "checkout_phone":
            if not self.is_valid_phone(text):
                await update.message.reply_text(
                    "Введите корректный номер телефона.",
                    reply_markup=self.cancel_keyboard(),
                )
                return
            draft["phone"] = text
            context.user_data["draft"] = draft
            self.set_state(context, "checkout_name", **draft)
            await update.message.reply_text("Как к вам можно обращаться?", reply_markup=self.cancel_keyboard())
            return

        if state == "checkout_name":
            if not self.is_valid_name(text):
                await update.message.reply_text(
                    "Имя не должно быть пустым.",
                    reply_markup=self.cancel_keyboard(),
                )
                return
            draft["name"] = text
            context.user_data["draft"] = draft
            self.set_state(context, "checkout_address", **draft)
            await update.message.reply_text("Введите адрес доставки:", reply_markup=self.cancel_keyboard())
            return

        if state == "checkout_address":
            if not self.is_valid_address(text):
                await update.message.reply_text(
                    "Адрес не должен быть пустым.",
                    reply_markup=self.cancel_keyboard(),
                )
                return
            draft["address"] = text
            context.user_data["draft"] = draft
            self.set_state(context, "checkout_comment", **draft)
            await update.message.reply_text("Введите комментарий к заказу или напишите «нет»:", reply_markup=self.cancel_keyboard())
            return

        if state == "checkout_comment":
            comment = "" if text.lower() == "нет" else text
            order_id = self.catalog.create_order(
                user_id,
                draft["name"],
                draft["phone"],
                draft["address"],
                comment,
            )
            order = self.catalog.get_order(order_id)
            items = self.catalog.get_order_items(order_id)
            self.clear_state(context)
            await self.send_main_menu(update.message, context, user_id, f"✅ Заказ #{order_id} оформлен.")

            await context.bot.send_message(
                chat_id=self.admin_id,
                text=self.format_order_text(order, items),
                parse_mode="HTML",
                reply_markup=self.order_keyboard(order_id),
            )
            return

        if self.is_admin(user_id):
            if state == "admin_add_category_name":
                self.catalog.add_category(text)
                self.clear_state(context)
                await update.message.reply_text("✅ Категория добавлена.", reply_markup=self.main_keyboard(user_id))
                return

            if state == "admin_rename_category_name":
                self.catalog.rename_category(draft["category_id"], text)
                self.clear_state(context)
                await update.message.reply_text("✅ Категория обновлена.", reply_markup=self.main_keyboard(user_id))
                return

            if state == "admin_add_product_name":
                draft["name"] = text
                self.set_state(context, "admin_add_product_desc", **draft)
                await update.message.reply_text("Шаг 2/4. Введите описание товара:", reply_markup=self.cancel_keyboard())
                return

            if state == "admin_add_product_desc":
                draft["description"] = text
                self.set_state(context, "admin_add_product_price", **draft)
                await update.message.reply_text("Шаг 3/4. Введите цену. Например: 1990 или 1990.50", reply_markup=self.cancel_keyboard())
                return

            if state == "admin_add_product_price":
                try:
                    price = float(text.replace(",", "."))
                except ValueError:
                    await update.message.reply_text("Не удалось распознать цену. Введите число.")
                    return
                draft["price"] = price
                self.set_state(context, "admin_add_product_photo", **draft)
                await update.message.reply_text("Шаг 4/4. Отправьте фото товара одним сообщением.", reply_markup=self.cancel_keyboard())
                return

            if state == "admin_edit_product_name":
                draft["name"] = text
                draft["edit_field"] = "name"
                product = self.catalog.get_product(int(draft["product_id"]))
                self.set_state(context, "admin_edit_product_confirm", **draft)
                await self.send_product_preview(
                    update.message,
                    self.build_product_preview(draft, product=product),
                    "Предпросмотр изменений товара:",
                    self.product_preview_keyboard(
                        "admprod:saveedit",
                        f"admprod:canceledit:{draft['product_id']}",
                    ),
                )
                return

            if state == "admin_edit_product_desc":
                draft["description"] = text
                draft["edit_field"] = "description"
                product = self.catalog.get_product(int(draft["product_id"]))
                self.set_state(context, "admin_edit_product_confirm", **draft)
                await self.send_product_preview(
                    update.message,
                    self.build_product_preview(draft, product=product),
                    "Предпросмотр изменений товара:",
                    self.product_preview_keyboard(
                        "admprod:saveedit",
                        f"admprod:canceledit:{draft['product_id']}",
                    ),
                )
                return

            if state == "admin_edit_product_price":
                try:
                    price = float(text.replace(",", "."))
                except ValueError:
                    await update.message.reply_text("Не удалось распознать цену. Введите число.")
                    return
                draft["price"] = price
                draft["edit_field"] = "price"
                product = self.catalog.get_product(int(draft["product_id"]))
                self.set_state(context, "admin_edit_product_confirm", **draft)
                await self.send_product_preview(
                    update.message,
                    self.build_product_preview(draft, product=product),
                    "Предпросмотр изменений товара:",
                    self.product_preview_keyboard(
                        "admprod:saveedit",
                        f"admprod:canceledit:{draft['product_id']}",
                    ),
                )
                return

            if state == "admin_set_contacts":
                self.catalog.set_contacts_text(text)
                self.clear_state(context)
                await update.message.reply_text("✅ Контакты обновлены.", reply_markup=self.main_keyboard(user_id))
                return

        # menu buttons
        if text == "🛍 Каталог":
            categories = self.catalog.list_categories()
            if not categories:
                await update.message.reply_text("Каталог пока пуст. Категории ещё не добавлены.")
                return
            await update.message.reply_text("Выберите раздел:", reply_markup=self.categories_keyboard(admin=False))
            return

        if text == "🛒 Корзина":
            await update.message.reply_text(
                self.format_cart_text(user_id),
                parse_mode="HTML",
                reply_markup=self.cart_keyboard(user_id) if self.catalog.get_cart(user_id) else self.main_keyboard(user_id),
            )
            return

        if text == "ℹ️ Контакты":
            if self.is_admin(user_id):
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ Изменить контакты", callback_data="contacts:edit")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="nav:main")],
                ])
                await update.message.reply_text(self.catalog.get_contacts_text(), reply_markup=kb)
            else:
                await update.message.reply_text(self.catalog.get_contacts_text(), reply_markup=self.main_keyboard(user_id))
            return

        if not self.is_admin(user_id):
            await update.message.reply_text("Используйте кнопки меню ниже.", reply_markup=self.main_keyboard(user_id))
            return

        if text == "📂 Категории":
            await update.message.reply_text("Управление категориями:", reply_markup=self.categories_keyboard(admin=True))
            return

        if text == "📦 Товары":
            await update.message.reply_text("Управление товарами:", reply_markup=self.admin_products_keyboard())
            return

        if text == "📬 Заказы":
            await self.show_orders(update.message, context, archived=False)
            return

        if text == "🗃 Архив заказов":
            await self.show_orders(update.message, context, archived=True)
            return

        await update.message.reply_text("Используйте кнопки меню ниже.", reply_markup=self.main_keyboard(user_id))

    async def photo_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not self.is_admin(user_id):
            await update.message.reply_text("Фото как сообщение здесь не используется. Выберите действие в меню.")
            return

        state = context.user_data.get("state")
        draft = context.user_data.get("draft", {})
        if not update.message.photo:
            await update.message.reply_text("Не вижу фото. Попробуйте ещё раз.")
            return
        photo_file_id = update.message.photo[-1].file_id

        if state == "admin_add_product_photo":
            draft["photo_file_id"] = photo_file_id
            self.set_state(context, "admin_add_product_confirm", **draft)
            await self.send_product_preview(
                update.message,
                self.build_product_preview(draft),
                "Предпросмотр нового товара:",
                self.product_preview_keyboard("admprod:saveadd", "admprod:canceladd"),
            )
            return

        if state == "admin_edit_product_photo":
            draft["photo_file_id"] = photo_file_id
            draft["edit_field"] = "photo"
            product = self.catalog.get_product(int(draft["product_id"]))
            self.set_state(context, "admin_edit_product_confirm", **draft)
            await self.send_product_preview(
                update.message,
                self.build_product_preview(draft, product=product),
                "Предпросмотр изменений товара:",
                self.product_preview_keyboard(
                    "admprod:saveedit",
                    f"admprod:canceledit:{draft['product_id']}",
                ),
            )
            return

        await update.message.reply_text("Сейчас фото не ожидается. Выберите действие в меню.")

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        # navigation
        if query.data == "nav:main":
            self.clear_state(context)
            await query.message.reply_text("Главное меню", reply_markup=self.main_keyboard(user_id))
            return

        # storefront
        if query.data.startswith("cat:"):
            category_id = int(query.data.split(":")[1])
            category = self.catalog.get_category(category_id)
            products = self.catalog.list_products(category_id)
            if not products:
                await self.edit_or_send_message(
                    query,
                    f"В разделе «{category['name']}» пока нет товаров.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ К разделам", callback_data="catalog:back")]
                    ]),
                )
                return
            await self.edit_or_send_message(
                query,
                f"Раздел: {category['name']}\n\nВыберите товар:",
                reply_markup=self.products_keyboard(category_id),
            )
            return

        if query.data == "catalog:back":
            await self.edit_or_send_message(
                query,
                "Выберите раздел:",
                reply_markup=self.categories_keyboard(admin=False),
            )
            return

        if query.data.startswith("prodview:"):
            product_id = int(query.data.split(":")[1])
            product = self.catalog.get_product(product_id)
            if not product:
                await self.edit_or_send_message(query, "Товар не найден.")
                return
            await self.show_product_message(
                query,
                context,
                product,
                self.format_product_compact(product),
                self.product_compact_keyboard(product),
            )
            return

        if query.data.startswith("prodfull:"):
            product_id = int(query.data.split(":")[1])
            product = self.catalog.get_product(product_id)
            if not product:
                await self.edit_or_send_message(query, "Товар не найден.")
                return
            await self.show_product_message(
                query,
                context,
                product,
                self.format_product_full(product),
                self.product_detail_keyboard(product),
            )
            return

        if query.data.startswith("prodadd:"):
            product_id = int(query.data.split(":")[1])
            self.catalog.add_to_cart(user_id, product_id)
            await query.answer("Товар добавлен в корзину.")
            return

        if query.data == "cart:open":
            cart = self.catalog.get_cart(user_id)
            await self.edit_or_send_message(
                query,
                self.format_cart_text(user_id),
                parse_mode="HTML",
                reply_markup=self.cart_keyboard(user_id) if cart else InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛍 Каталог", callback_data="catalog:back")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="nav:main")],
                ]),
            )
            return

        # cart
        if query.data.startswith("cart:inc:"):
            product_id = int(query.data.split(":")[2])
            self.catalog.change_cart_quantity(user_id, product_id, 1)
            await self.edit_or_send_message(
                query,
                self.format_cart_text(user_id),
                parse_mode="HTML",
                reply_markup=self.cart_keyboard(user_id),
            )
            return

        if query.data.startswith("cart:dec:"):
            product_id = int(query.data.split(":")[2])
            self.catalog.change_cart_quantity(user_id, product_id, -1)
            if self.catalog.get_cart(user_id):
                await self.edit_or_send_message(
                    query,
                    self.format_cart_text(user_id),
                    parse_mode="HTML",
                    reply_markup=self.cart_keyboard(user_id),
                )
            else:
                await self.edit_or_send_message(
                    query,
                    "🛒 Корзина пуста.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🛍 Каталог", callback_data="catalog:back")],
                        [InlineKeyboardButton("🏠 Главное меню", callback_data="nav:main")],
                    ]),
                )
            return

        if query.data.startswith("cart:rm:"):
            product_id = int(query.data.split(":")[2])
            self.catalog.remove_from_cart(user_id, product_id)
            if self.catalog.get_cart(user_id):
                await self.edit_or_send_message(
                    query,
                    self.format_cart_text(user_id),
                    parse_mode="HTML",
                    reply_markup=self.cart_keyboard(user_id),
                )
            else:
                await self.edit_or_send_message(
                    query,
                    "🛒 Корзина пуста.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🛍 Каталог", callback_data="catalog:back")],
                        [InlineKeyboardButton("🏠 Главное меню", callback_data="nav:main")],
                    ]),
                )
            return

        if query.data == "checkout:start":
            if not self.catalog.get_cart(user_id):
                await query.message.reply_text("Корзина пуста.")
                return
            self.set_state(context, "checkout_phone")
            phone_keyboard = ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Отправить номер", request_contact=True)], ["↩️ Отмена"]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await query.message.reply_text("Введите номер телефона или отправьте его кнопкой ниже:", reply_markup=phone_keyboard)
            return

        # admin-only
        if not self.is_admin(user_id):
            await query.message.reply_text("Это действие доступно только администратору.")
            return

        if query.data == "admcat:list":
            await query.message.reply_text("Управление категориями:", reply_markup=self.categories_keyboard(admin=True))
            return

        if query.data == "admcat:add":
            self.set_state(context, "admin_add_category_name")
            await query.message.reply_text("Введите название новой категории:", reply_markup=self.cancel_keyboard())
            return

        if query.data.startswith("admcatopen:"):
            category_id = int(query.data.split(":")[1])
            category = self.catalog.get_category(category_id)
            await query.message.reply_text(
                f"Категория: {category['name']}",
                reply_markup=self.admin_category_manage_keyboard(category_id),
            )
            return

        if query.data.startswith("admcat:rename:"):
            category_id = int(query.data.split(":")[2])
            self.set_state(context, "admin_rename_category_name", category_id=category_id)
            await query.message.reply_text("Введите новое название категории:", reply_markup=self.cancel_keyboard())
            return

        if query.data.startswith("admcat:delete:"):
            category_id = int(query.data.split(":")[2])
            self.catalog.delete_category(category_id)
            await query.message.reply_text("✅ Категория удалена.")
            await query.message.reply_text("Управление категориями:", reply_markup=self.categories_keyboard(admin=True))
            return

        if query.data == "admprod:list":
            await query.message.reply_text("Управление товарами:", reply_markup=self.admin_products_keyboard())
            return

        if query.data == "admprod:add":
            categories = self.catalog.list_categories()
            if not categories:
                await query.message.reply_text("Сначала добавьте хотя бы одну категорию.")
                return
            rows = [[InlineKeyboardButton(cat['name'], callback_data=f"admprod:addcat:{cat['id']}")] for cat in categories]
            rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="admprod:list")])
            await query.message.reply_text("Выберите категорию для нового товара:", reply_markup=InlineKeyboardMarkup(rows))
            return

        if query.data.startswith("admprod:addcat:"):
            category_id = int(query.data.split(":")[2])
            self.set_state(context, "admin_add_product_name", category_id=category_id)
            await query.message.reply_text("Шаг 1/4. Введите название товара:", reply_markup=self.cancel_keyboard())
            return

        if query.data.startswith("admprod:view:"):
            product_id = int(query.data.split(":")[2])
            product = self.catalog.get_product(product_id)
            await query.message.reply_text(
                self.format_product_full(product),
                parse_mode="HTML",
                reply_markup=self.admin_product_manage_keyboard(product_id),
            )
            return

        if query.data.startswith("admprod:editname:"):
            product_id = int(query.data.split(":")[2])
            product = self.catalog.get_product(product_id)
            self.set_state(context, "admin_edit_product_name", product_id=product_id)
            await query.message.reply_text(
                f"Текущее название: {product['name']}\n\nВведите новое название:",
                reply_markup=self.cancel_keyboard(),
            )
            return

        if query.data.startswith("admprod:editdesc:"):
            product_id = int(query.data.split(":")[2])
            product = self.catalog.get_product(product_id)
            self.set_state(context, "admin_edit_product_desc", product_id=product_id)
            await query.message.reply_text(
                f"Текущее описание:\n{product['description'] or '—'}\n\nВведите новое описание:",
                reply_markup=self.cancel_keyboard(),
            )
            return

        if query.data.startswith("admprod:editprice:"):
            product_id = int(query.data.split(":")[2])
            product = self.catalog.get_product(product_id)
            self.set_state(context, "admin_edit_product_price", product_id=product_id)
            await query.message.reply_text(
                f"Текущая цена: {product['price']:.2f}\n\nВведите новую цену:",
                reply_markup=self.cancel_keyboard(),
            )
            return

        if query.data.startswith("admprod:editphoto:"):
            product_id = int(query.data.split(":")[2])
            product = self.catalog.get_product(product_id)
            self.set_state(context, "admin_edit_product_photo", product_id=product_id)
            await query.message.reply_text(
                f"Текущее фото: {'загружено' if product['photo_file_id'] else 'не загружено'}\n\nОтправьте новое фото товара:",
                reply_markup=self.cancel_keyboard(),
            )
            return

        if query.data == "admprod:saveadd":
            draft = context.user_data.get("draft", {})
            self.catalog.add_product(
                category_id=int(draft["category_id"]),
                name=draft["name"],
                description=draft["description"],
                price=float(draft["price"]),
                photo_file_id=draft["photo_file_id"],
            )
            self.clear_state(context)
            await query.message.reply_text("✅ Товар добавлен.")
            await query.message.reply_text("Управление товарами:", reply_markup=self.admin_products_keyboard())
            return

        if query.data == "admprod:canceladd":
            self.clear_state(context)
            await query.message.reply_text("Действие отменено.")
            await query.message.reply_text("Управление товарами:", reply_markup=self.admin_products_keyboard())
            return

        if query.data == "admprod:saveedit":
            draft = context.user_data.get("draft", {})
            product_id = int(draft["product_id"])
            edit_field = draft.get("edit_field")
            if edit_field == "name":
                self.catalog.update_product_name(product_id, draft["name"])
            elif edit_field == "description":
                self.catalog.update_product_description(product_id, draft["description"])
            elif edit_field == "price":
                self.catalog.update_product_price(product_id, float(draft["price"]))
            elif edit_field == "photo":
                self.catalog.update_product_photo(product_id, draft["photo_file_id"])
            self.clear_state(context)
            product = self.catalog.get_product(product_id)
            await query.message.reply_text("✅ Товар обновлён.")
            await query.message.reply_text(
                self.format_product_full(product),
                parse_mode="HTML",
                reply_markup=self.admin_product_manage_keyboard(product_id),
            )
            return

        if query.data.startswith("admprod:canceledit:"):
            product_id = int(query.data.split(":")[2])
            self.clear_state(context)
            product = self.catalog.get_product(product_id)
            await query.message.reply_text("Действие отменено.")
            await query.message.reply_text(
                self.format_product_full(product),
                parse_mode="HTML",
                reply_markup=self.admin_product_manage_keyboard(product_id),
            )
            return

        if query.data.startswith("admprod:movecat:"):
            product_id = int(query.data.split(":")[2])
            rows = [[InlineKeyboardButton(cat['name'], callback_data=f"admprod:setcat:{product_id}:{cat['id']}")] for cat in self.catalog.list_categories()]
            rows.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"admprod:view:{product_id}")])
            await query.message.reply_text("Выберите новую категорию:", reply_markup=InlineKeyboardMarkup(rows))
            return

        if query.data.startswith("admprod:setcat:"):
            _, _, product_id, category_id = query.data.split(":")
            self.catalog.update_product_category(int(product_id), int(category_id))
            await query.message.reply_text("✅ Категория товара обновлена.")
            await query.message.reply_text("Управление товарами:", reply_markup=self.admin_products_keyboard())
            return

        if query.data.startswith("admprod:delete:"):
            product_id = int(query.data.split(":")[2])
            self.catalog.delete_product(product_id)
            await query.message.reply_text("✅ Товар удалён.")
            await query.message.reply_text("Управление товарами:", reply_markup=self.admin_products_keyboard())
            return

        if query.data == "orders:list":
            await self.show_orders(query.message, context, archived=False)
            return

        if query.data == "orders:archive":
            await self.show_orders(query.message, context, archived=True)
            return

        if query.data.startswith("order:"):
            _, status, order_id = query.data.split(":")
            self.catalog.update_order_status(int(order_id), status)
            order = self.catalog.get_order(int(order_id))
            items = self.catalog.get_order_items(int(order_id))
            archived = self.catalog.is_final_order_status(order["status"])
            await query.message.reply_text(
                self.format_order_text(order, items),
                parse_mode="HTML",
                reply_markup=self.order_keyboard(int(order_id), archived=archived),
            )
            return

        if query.data == "contacts:edit":
            self.set_state(context, "admin_set_contacts")
            await query.message.reply_text("Введите новый текст для раздела «Контакты»:", reply_markup=self.cancel_keyboard())
            return

    async def contact_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        state = context.user_data.get("state")
        if state != "checkout_phone":
            return

        contact = update.message.contact
        if not contact:
            return

        draft = context.user_data.get("draft", {})
        if not self.is_valid_phone(contact.phone_number):
            await update.message.reply_text(
                "Введите корректный номер телефона.",
                reply_markup=self.cancel_keyboard()
            )
            return

        draft["phone"] = contact.phone_number

        self.set_state(context, "checkout_name", **draft)
        await update.message.reply_text(
            "Как к вам можно обращаться?",
            reply_markup=self.cancel_keyboard()
        )

    async def show_orders(self, target, context: ContextTypes.DEFAULT_TYPE, archived: bool = False):
        orders = self.catalog.list_archived_orders() if archived else self.catalog.list_active_orders()
        if not orders:
            empty_text = "Архив заказов пока пуст." if archived else "Активных заказов пока нет."
            await target.reply_text(empty_text, reply_markup=self.orders_section_keyboard(archived=archived))
            return

        title = "Архив заказов:" if archived else "Активные заказы:"
        await target.reply_text(title, reply_markup=self.orders_section_keyboard(archived=archived))
        for order in orders[:20]:
            items = self.catalog.get_order_items(int(order["id"]))
            await target.reply_text(
                self.format_order_text(order, items),
                parse_mode="HTML",
                reply_markup=self.order_keyboard(
                    int(order["id"]),
                    archived=self.catalog.is_final_order_status(order["status"]),
                ),
            )

    def build_app(self) -> Application:
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CallbackQueryHandler(self.callback_handler))
        app.add_handler(MessageHandler(filters.CONTACT, self.contact_handler))
        app.add_handler(MessageHandler(filters.PHOTO, self.photo_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_handler))
        return app
