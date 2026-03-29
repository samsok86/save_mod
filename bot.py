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


def save_to_cache(message: Message):
    cid = message.chat.id
    if cid not in cache:
        cache[cid] = {}
    cache[cid][message.message_id] = message


async def forward_to_admin(msg: Message, prefix: str = ""):
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
        await bot.send_message(ADMIN_ID, header)

        if msg.text:
            await bot.send_message(ADMIN_ID, f"✉️ {msg.text}")
        if msg.voice:
            await bot.send_voice(ADMIN_ID, msg.voice.file_id)
        if msg.video_note:
            await bot.send_video_note(ADMIN_ID, msg.video_note.file_id)
        if msg.photo:
            await bot.send_photo(ADMIN_ID, msg.photo[-1].file_id, caption=msg.caption)
        if msg.video:
            await bot.send_video(ADMIN_ID, msg.video.file_id, caption=msg.caption)
        if msg.audio:
            await bot.send_audio(ADMIN_ID, msg.audio.file_id, caption=msg.caption)
        if msg.document:
            await bot.send_document(ADMIN_ID, msg.document.file_id, caption=msg.caption)
        if msg.sticker:
            await bot.send_sticker(ADMIN_ID, msg.sticker.file_id)
        if msg.animation:
            await bot.send_animation(ADMIN_ID, msg.animation.file_id, caption=msg.caption)
    except Exception as e:
        logging.error(f"Ошибка пересылки: {e}")


@dp.business_message()
async def handle_business_message(message: Message):
    save_to_cache(message)

    if (
        message.from_user
        and message.from_user.id == ADMIN_ID
        and message.reply_to_message
    ):
        replied = message.reply_to_message
        cid = message.chat.id
        if cid in cache and replied.message_id in cache[cid]:
            original = cache[cid][replied.message_id]
            if original.photo or original.video or original.video_note or original.voice:
                await forward_to_admin(original, prefix="👁 Одноразка:")


@dp.edited_business_message()
async def handle_edited(message: Message):
    save_to_cache(message)


@dp.deleted_business_messages()
async def handle_deleted(event: BusinessMessagesDeleted):
    cid = event.chat.id
    for msg_id in event.message_ids:
        if cid in cache and msg_id in cache[cid]:
            msg = cache[cid][msg_id]
            await forward_to_admin(msg, prefix="🗑 Удалено:")
            del cache[cid][msg_id]


@dp.business_connection()
async def handle_connection(bc: BusinessConnection):
    if bc.user.id == ADMIN_ID:
        if bc.is_enabled:
            await bot.send_message(ADMIN_ID, "✅ Бот подключён к Business аккаунту!")
        else:
            await bot.send_message(ADMIN_ID, "❌ Бот отключён от Business аккаунта.")


@dp.message(Command("start"))
async def start(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "✅ Бот активен!\n\n"
        "Чтобы подключить:\n"
        "Настройки → Telegram Business → Чат-боты → выбери этого бота\n\n"
        "После этого бот будет:\n"
        "🗑 Пересылать удалённые сообщения\n"
        "👁 Сохранять одноразки (ответь на них любым текстом)\n"
        "📎 Перехватывать голосовые, кружки, фото, видео"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
