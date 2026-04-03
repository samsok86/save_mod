import os
import asyncio
import logging
import time
from collections import OrderedDict
from aiogram import Bot, Dispatcher
from aiogram.types import Message, BusinessMessagesDeleted, BusinessConnection
from aiogram.filters import Command
from aiogram.exceptions import TelegramRetryAfter
from fun import cmd_spam, cmd_stop, cmd_fuck, get_like_suffix

logging.basicConfig(level=logging.INFO)

TOKEN2 = os.getenv("TOKEN2")
_admin_raw = os.getenv("ADMIN_ID", "")
if not TOKEN2:
    raise ValueError("TOKEN2 не задан в переменных окружения")
if not _admin_raw or not "".join(filter(str.isdigit, _admin_raw)):
    raise ValueError("ADMIN_ID не задан или содержит некорректное значение")

ADMIN_ID = int("".join(filter(str.isdigit, _admin_raw)))

bot = Bot(token=TOKEN2)
dp = Dispatcher()

MAX_CACHE_PER_CHAT = 100
CACHE_TTL_SECONDS = 7 * 24 * 3600

cache: dict[int, OrderedDict] = {}

connected_users: dict[int, dict] = {}
connection_owners: dict[str, int] = {}
banned_users: set[int] = set()
stats: dict[str, int] = {"deleted": 0, "edited": 0, "connections": 0}

like_mode_chats: set[int] = set()
like_edited_messages: set[tuple[int, int]] = set()


async def cache_cleanup_task():
    while True:
        await asyncio.sleep(3600)
        now = time.time()
        cutoff = now - CACHE_TTL_SECONDS
        for cid in list(cache.keys()):
            expired = [mid for mid, (_, ts) in cache[cid].items() if ts < cutoff]
            for mid in expired:
                del cache[cid][mid]
            if not cache[cid]:
                del cache[cid]
        logging.info("Кэш очищен от сообщений старше 7 дней")


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def save_to_cache(message: Message):
    cid = message.chat.id
    if cid not in cache:
        cache[cid] = OrderedDict()
    cache[cid][message.message_id] = (message, time.time())
    while len(cache[cid]) > MAX_CACHE_PER_CHAT:
        cache[cid].popitem(last=False)


def get_cached_message(chat_id: int, msg_id: int) -> Message | None:
    if chat_id in cache and msg_id in cache[chat_id]:
        msg, _ = cache[chat_id][msg_id]
        return msg
    return None


def get_command(text: str) -> str:
    if not text or not text.startswith("/"):
        return ""
    word = text.split()[0]
    return word.lstrip("/").split("@")[0].lower()


async def resolve_owner(business_connection_id: str) -> int:
    if business_connection_id in connection_owners:
        return connection_owners[business_connection_id]
    try:
        bc = await bot.get_business_connection(business_connection_id)
        owner_id = bc.user.id
        connection_owners[business_connection_id] = owner_id
        connected_users[owner_id] = {
            "name": bc.user.full_name,
            "username": bc.user.username or "",
        }
        logging.info(f"Восстановлен owner_id={owner_id} для bc_id={business_connection_id}")
        return owner_id
    except Exception as e:
        logging.warning(f"Не удалось получить бизнес-подключение {business_connection_id}: {e}")
        return ADMIN_ID


def build_sender_info(msg: Message) -> tuple[str, str]:
    name = "Unknown"
    uid = "Unknown"
    if msg.from_user:
        name = escape_html(msg.from_user.full_name)
        if msg.from_user.username:
            name += f", @{msg.from_user.username}"
        uid = str(msg.from_user.id)
    return name, uid


def build_deleted_header(msg: Message) -> str:
    name, uid = build_sender_info(msg)
    return (
        f'<tg-emoji emoji-id="5904630315946611415">👤</tg-emoji> {name}\n'
        f'<tg-emoji emoji-id="5285350148451344065">📱</tg-emoji> {uid}\n'
        f'<tg-emoji emoji-id="5366573795404447728">🗑</tg-emoji> это сообщение было удалено:'
    )


def build_deleted_header_admin(msg: Message, owner_id: int) -> str:
    name, uid = build_sender_info(msg)
    info = connected_users.get(owner_id)
    if info:
        owner_display = escape_html(info["name"])
        if info.get("username"):
            owner_display += f", @{info['username']}"
        owner_display += f" [ID: {owner_id}]"
    else:
        owner_display = str(owner_id)
    return (
        f'<tg-emoji emoji-id="5904630315946611415">👤</tg-emoji> {name}\n'
        f'<tg-emoji emoji-id="5285350148451344065">📱</tg-emoji> {uid}\n'
        f'📨 Получатель: {owner_display}\n'
        f'<tg-emoji emoji-id="5366573795404447728">🗑</tg-emoji> это сообщение было удалено:'
    )


async def send_deleted_msg(user_id: int, msg: Message, header_html: str):
    try:
        if msg.text:
            full = f"{header_html}\n<blockquote>{escape_html(msg.text)}</blockquote>"
            await bot.send_message(user_id, full, parse_mode="HTML")
        elif msg.photo:
            caption = header_html + (f"\n{escape_html(msg.caption)}" if msg.caption else "")
            await bot.send_photo(user_id, msg.photo[-1].file_id, caption=caption, parse_mode="HTML")
        elif msg.video:
            caption = header_html + (f"\n{escape_html(msg.caption)}" if msg.caption else "")
            await bot.send_video(user_id, msg.video.file_id, caption=caption, parse_mode="HTML")
        elif msg.voice:
            await bot.send_voice(user_id, msg.voice.file_id, caption=header_html, parse_mode="HTML")
        elif msg.audio:
            caption = header_html + (f"\n{escape_html(msg.caption)}" if msg.caption else "")
            await bot.send_audio(user_id, msg.audio.file_id, caption=caption, parse_mode="HTML")
        elif msg.document:
            caption = header_html + (f"\n{escape_html(msg.caption)}" if msg.caption else "")
            await bot.send_document(user_id, msg.document.file_id, caption=caption, parse_mode="HTML")
        elif msg.video_note:
            await bot.send_message(user_id, header_html, parse_mode="HTML")
            await bot.send_video_note(user_id, msg.video_note.file_id)
        elif msg.sticker:
            await bot.send_message(user_id, header_html, parse_mode="HTML")
            await bot.send_sticker(user_id, msg.sticker.file_id)
        elif msg.animation:
            await bot.send_message(user_id, header_html, parse_mode="HTML")
            await bot.send_animation(user_id, msg.animation.file_id)
        elif msg.contact:
            c = msg.contact
            cname = escape_html(f"{c.first_name} {c.last_name or ''}".strip())
            full = f"{header_html}\n📞 Контакт: {cname} — {c.phone_number}"
            await bot.send_message(user_id, full, parse_mode="HTML")
        elif msg.location:
            await bot.send_message(user_id, header_html, parse_mode="HTML")
            await bot.send_location(user_id, msg.location.latitude, msg.location.longitude)
        else:
            await bot.send_message(user_id, header_html, parse_mode="HTML")
            try:
                await bot.copy_message(user_id, msg.chat.id, msg.message_id)
            except Exception:
                pass
    except Exception as e:
        logging.error(f"Ошибка отправки удалённого сообщения пользователю {user_id}: {e}")


async def forward_deleted(msg: Message, owner_id: int):
    stats["deleted"] += 1
    await send_deleted_msg(owner_id, msg, build_deleted_header(msg))
    if owner_id != ADMIN_ID:
        await send_deleted_msg(ADMIN_ID, msg, build_deleted_header_admin(msg, owner_id))


@dp.business_connection()
async def handle_connection(bc: BusinessConnection):
    user_id = bc.user.id
    if bc.is_enabled:
        if user_id in banned_users:
            await bot.send_message(user_id, "🚫 Вы заблокированы и не можете пользоваться ботом.")
            return
        connection_owners[bc.id] = user_id
        connected_users[user_id] = {
            "name": bc.user.full_name,
            "username": bc.user.username or "",
        }
        stats["connections"] += 1
        await bot.send_message(user_id, "✅ Бот подключён! Теперь я сохраняю удалённые сообщения.")
        if user_id != ADMIN_ID:
            uname = f" (@{bc.user.username})" if bc.user.username else ""
            await bot.send_message(
                ADMIN_ID,
                f"🔔 Новый пользователь подключился:\n👤 {bc.user.full_name}{uname}\n🆔 {bc.user.id}"
            )
    else:
        connection_owners.pop(bc.id, None)
        connected_users.pop(user_id, None)
        await bot.send_message(user_id, "❌ Бот отключён от Business аккаунта.")


@dp.business_message()
async def handle_business_message(message: Message):
    if not message.business_connection_id:
        return

    owner_id = await resolve_owner(message.business_connection_id)

    if owner_id in banned_users:
        return

    sender_id = message.from_user.id if message.from_user else None
    cmd = get_command(message.text or "")

    if cmd in ("spam", "fuck", "stop", "like", "nolike"):
        if sender_id != owner_id:
            save_to_cache(message)
            return
        if cmd == "spam":
            await cmd_spam(message, bot)
        elif cmd == "fuck":
            await cmd_fuck(message, bot)
        elif cmd == "stop":
            await cmd_stop(message, bot)
        elif cmd == "like":
            chat_id = message.chat.id
            try:
                await bot.delete_messages(
                    chat_id=chat_id,
                    message_ids=[message.message_id],
                    business_connection_id=message.business_connection_id,
                )
            except Exception as e:
                logging.warning(f"Не удалось удалить /like: {e}")
            like_mode_chats.add(chat_id)
            try:
                await bot.send_message(
                    chat_id,
                    '<tg-emoji emoji-id="5249009601231224691">❤</tg-emoji>|режим лайкера активирован.',
                    parse_mode="HTML",
                    business_connection_id=message.business_connection_id,
                )
            except Exception as e:
                logging.error(f"Ошибка отправки like-статуса: {e}")
        elif cmd == "nolike":
            chat_id = message.chat.id
            try:
                await bot.delete_messages(
                    chat_id=chat_id,
                    message_ids=[message.message_id],
                    business_connection_id=message.business_connection_id,
                )
            except Exception as e:
                logging.warning(f"Не удалось удалить /nolike: {e}")
            like_mode_chats.discard(chat_id)
            try:
                await bot.send_message(
                    chat_id,
                    '<tg-emoji emoji-id="5249009601231224691">❤</tg-emoji>|режим лайкера выключен',
                    parse_mode="HTML",
                    business_connection_id=message.business_connection_id,
                )
            except Exception as e:
                logging.error(f"Ошибка отправки nolike-статуса: {e}")
        return

    save_to_cache(message)

    if sender_id == owner_id and message.chat.id in like_mode_chats:
        suffix = get_like_suffix()
        like_key = (message.chat.id, message.message_id)
        like_edited_messages.add(like_key)
        try:
            if message.text:
                await bot.edit_message_text(
                    text=message.text + suffix,
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    business_connection_id=message.business_connection_id,
                    parse_mode="HTML",
                )
            elif message.caption:
                await bot.edit_message_caption(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    caption=message.caption + suffix,
                    business_connection_id=message.business_connection_id,
                    parse_mode="HTML",
                )
            else:
                like_edited_messages.discard(like_key)
        except TelegramRetryAfter as e:
            logging.warning(f"FloodWait {e.retry_after}s при лайкере, повтор...")
            await asyncio.sleep(e.retry_after + 0.5)
            try:
                if message.text:
                    await bot.edit_message_text(
                        text=message.text + suffix,
                        chat_id=message.chat.id,
                        message_id=message.message_id,
                        business_connection_id=message.business_connection_id,
                        parse_mode="HTML",
                    )
                elif message.caption:
                    await bot.edit_message_caption(
                        chat_id=message.chat.id,
                        message_id=message.message_id,
                        caption=message.caption + suffix,
                        business_connection_id=message.business_connection_id,
                        parse_mode="HTML",
                    )
            except Exception as e2:
                logging.warning(f"Повторная ошибка лайкера: {e2}")
                like_edited_messages.discard(like_key)
        except Exception as e:
            logging.warning(f"Не удалось добавить суффикс лайкера: {e}")
            like_edited_messages.discard(like_key)


@dp.edited_business_message()
async def handle_edited(message: Message):
    if not message.business_connection_id:
        return

    like_key = (message.chat.id, message.message_id)
    if like_key in like_edited_messages:
        like_edited_messages.discard(like_key)
        save_to_cache(message)
        return

    owner_id = await resolve_owner(message.business_connection_id)

    if owner_id in banned_users:
        return

    cid = message.chat.id
    old_text = ""
    old_msg = get_cached_message(cid, message.message_id)
    if old_msg:
        old_text = old_msg.text or old_msg.caption or ""

    new_text = message.text or message.caption or ""

    if (old_text or new_text) and old_text != new_text:
        stats["edited"] += 1
        name, uid = build_sender_info(message)
        edited_html = (
            f'<tg-emoji emoji-id="5904630315946611415">👤</tg-emoji> {name}\n'
            f'<tg-emoji emoji-id="5285350148451344065">📱</tg-emoji> {uid}\n'
            f'<b>Старый текст:</b>\n<blockquote>{escape_html(old_text)}</blockquote>\n'
            f'<b>Новый текст:</b>\n<blockquote>{escape_html(new_text)}</blockquote>'
        )
        try:
            await bot.send_message(owner_id, edited_html, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Ошибка отправки изменённого: {e}")

        if owner_id != ADMIN_ID:
            info = connected_users.get(owner_id)
            if info:
                owner_display = escape_html(info["name"])
                if info.get("username"):
                    owner_display += f", @{info['username']}"
                owner_display += f" [ID: {owner_id}]"
            else:
                owner_display = str(owner_id)
            admin_html = (
                f'<tg-emoji emoji-id="5904630315946611415">👤</tg-emoji> {name}\n'
                f'<tg-emoji emoji-id="5285350148451344065">📱</tg-emoji> {uid}\n'
                f'📨 Получатель: {owner_display}\n'
                f'<b>Старый текст:</b>\n<blockquote>{escape_html(old_text)}</blockquote>\n'
                f'<b>Новый текст:</b>\n<blockquote>{escape_html(new_text)}</blockquote>'
            )
            try:
                await bot.send_message(ADMIN_ID, admin_html, parse_mode="HTML")
            except Exception as e:
                logging.error(f"Ошибка копии изменённого для админа: {e}")

    save_to_cache(message)


@dp.deleted_business_messages()
async def handle_deleted_event(event: BusinessMessagesDeleted):
    if not event.business_connection_id:
        return

    owner_id = await resolve_owner(event.business_connection_id)

    if owner_id in banned_users:
        return

    cid = event.chat.id
    for msg_id in event.message_ids:
        msg = get_cached_message(cid, msg_id)
        if msg:
            await forward_deleted(msg, owner_id)
            if cid in cache and msg_id in cache[cid]:
                del cache[cid][msg_id]


START_TEXT = (
    '<tg-emoji emoji-id="5897948935971933748">👋</tg-emoji><b>Приветствую!</b>\n\n'
    '<b>Как подключить:</b>\n'
    'Настройки → Telegram Business → \n'
    'Чат-боты → введи @wrideny_direct_bot\n\n'
    '<b>После подключения \nбот будет:</b>\n'
    "<blockquote expandable>"
    '<tg-emoji emoji-id="5861559868506247215">🐸</tg-emoji>Пересылать Удаленные сообщения.\n'
    '<tg-emoji emoji-id="5866234163018861829">📷</tg-emoji>Пересылать удаленные фото/видео.\n'
    '<tg-emoji emoji-id="5357356263011290630">🎤</tg-emoji>Пересылать удаленные Голосовые сообщения и аудио.\n'
    '<tg-emoji emoji-id="5289505907267364732">🎭</tg-emoji>Пересылать удаленные GIF и Стикеры.\n'
    '<tg-emoji emoji-id="5197395463111727395">🎥</tg-emoji>Пересылать удаленные кружочки.'
    "</blockquote>\n\n"
    '<b>Пользуйтесь!</b> <tg-emoji emoji-id="6030400221232501136">🤖</tg-emoji>'
)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(START_TEXT, parse_mode="HTML")


@dp.message(Command("users"))
async def cmd_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not connected_users:
        await message.answer("👥 Нет подключённых пользователей.")
        return
    lines = ["👥 Подключённые пользователи:\n"]
    for uid, info in connected_users.items():
        ban_mark = " 🚫" if uid in banned_users else ""
        uname = f" (@{info['username']})" if info.get("username") else ""
        lines.append(f"• {info['name']}{uname} — 🆔 {uid}{ban_mark}")
    await message.answer("\n".join(lines))


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "📊 Статистика бота:\n\n"
        f"👥 Всего подключений: {stats['connections']}\n"
        f"🗑 Перехвачено удалённых: {stats['deleted']}\n"
        f"✏️ Перехвачено изменённых: {stats['edited']}\n"
        f"🔗 Сейчас подключено: {len(connected_users)}\n"
        f"🚫 Заблокировано: {len(banned_users)}"
    )


@dp.message(Command("ban"))
async def cmd_ban(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /ban <ID или @username>")
        return
    target = args[1].strip().lstrip("@")
    target_id = None
    if target.lstrip("-").isdigit():
        target_id = int(target)
    else:
        for uid, info in connected_users.items():
            if info.get("username", "").lower() == target.lower():
                target_id = uid
                break
    if target_id is None:
        await message.answer(f"❌ Пользователь '{target}' не найден среди подключённых.")
        return
    if target_id == ADMIN_ID:
        await message.answer("❌ Нельзя заблокировать администратора.")
        return
    banned_users.add(target_id)
    info = connected_users.get(target_id)
    name = info["name"] if info else str(target_id)
    await message.answer(f"🚫 Пользователь {name} (ID: {target_id}) заблокирован.")
    try:
        await bot.send_message(target_id, "🚫 Вы были заблокированы администратором.")
    except Exception:
        pass


@dp.message(Command("unban"))
async def cmd_unban(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /unban <ID или @username>")
        return
    target = args[1].strip().lstrip("@")
    target_id = None
    if target.lstrip("-").isdigit():
        target_id = int(target)
    else:
        for uid, info in connected_users.items():
            if info.get("username", "").lower() == target.lower():
                target_id = uid
                break
    if target_id is None:
        await message.answer(f"❌ Пользователь '{target}' не найден.")
        return
    if target_id in banned_users:
        banned_users.discard(target_id)
        info = connected_users.get(target_id)
        name = info["name"] if info else str(target_id)
        await message.answer(f"✅ Пользователь {name} (ID: {target_id}) разблокирован.")
        try:
            await bot.send_message(target_id, "✅ Вы были разблокированы администратором.")
        except Exception:
            pass
    else:
        await message.answer(f"ℹ️ Пользователь {target_id} не заблокирован.")


async def main():
    asyncio.create_task(cache_cleanup_task())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
