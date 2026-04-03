import asyncio
import logging
import random
from aiogram import Bot
from aiogram.types import Message, MessageEntity
from aiogram.exceptions import TelegramRetryAfter


spam_running: dict[int, bool] = {}

N_EMOJIS = [
    "5467706063178453976",
    "5366389751760851269",
    "5368428705880219702",
    "5368376753955806970",
    "5368808192010625717",
    "5368523530168180585",
    "5289505907267364732",
    "5402149709596861623",
    "5442823788624371882",
    "5415858570895846595",
]

A_EMOJIS = [
    "5211025120918785460",
    "5447614579829921377",
    "5211155151053675393",
    "5246899131611377553",
    "5395591955960851534",
    "5188439983853169383",
    "5310299561934207014",
    "5440740896989540064",
    "5442861262214030402",
    "5393305396976828658",
]


def get_display_name(user) -> str:
    if not user:
        return "Неизвестный"
    name = user.first_name or ""
    if user.last_name:
        name += f" {user.last_name}"
    if name.strip():
        return name.strip()
    if user.username:
        return f"@{user.username}"
    return str(user.id)


def get_like_suffix() -> str:
    n = random.choice(N_EMOJIS)
    a = random.choice(A_EMOJIS)
    return (
        f'.<tg-emoji emoji-id="{n}">❤</tg-emoji>'
        f'<tg-emoji emoji-id="{a}">❤</tg-emoji>'
    )


async def delete_command(message: Message, bot: Bot):
    try:
        await bot.delete_messages(
            chat_id=message.chat.id,
            message_ids=[message.message_id],
            business_connection_id=message.business_connection_id,
        )
    except Exception as e:
        logging.warning(f"Не удалось удалить команду: {e}")


async def cmd_spam(message: Message, bot: Bot):
    chat_id = message.chat.id
    raw = message.text or ""
    parts = raw.split(maxsplit=2)

    if spam_running.get(chat_id, False):
        try:
            await bot.send_message(
                chat_id,
                "⏳ Спам уже запущен. Дождитесь завершения или используйте /stop",
                business_connection_id=message.business_connection_id,
            )
        except Exception:
            pass
        return

    if len(parts) < 3:
        await bot.send_message(
            chat_id,
            "❌ Использование: /spam [кол-во 1–99] [текст до 200 символов]",
            business_connection_id=message.business_connection_id,
            reply_to_message_id=message.message_id,
        )
        return

    if not parts[1].isdigit():
        await bot.send_message(
            chat_id,
            "❌ Количество должно быть числом от 1 до 99",
            business_connection_id=message.business_connection_id,
            reply_to_message_id=message.message_id,
        )
        return

    count = max(1, min(int(parts[1]), 99))
    spam_text = parts[2]

    if len(spam_text) > 200:
        await bot.send_message(
            chat_id,
            "❌ Текст не должен превышать 200 символов",
            business_connection_id=message.business_connection_id,
            reply_to_message_id=message.message_id,
        )
        return

    text_offset = raw.index(spam_text)

    shifted_entities: list[MessageEntity] = []
    if message.entities:
        for ent in message.entities:
            ent_end = ent.offset + ent.length
            if ent_end > text_offset:
                new_offset = max(ent.offset - text_offset, 0)
                new_length = ent.length - max(text_offset - ent.offset, 0)
                if new_length > 0:
                    shifted_entities.append(MessageEntity(
                        type=ent.type,
                        offset=new_offset,
                        length=new_length,
                        url=getattr(ent, "url", None),
                        user=getattr(ent, "user", None),
                        language=getattr(ent, "language", None),
                        custom_emoji_id=getattr(ent, "custom_emoji_id", None),
                    ))

    await delete_command(message, bot)

    spam_running[chat_id] = True
    try:
        for _ in range(count):
            if not spam_running.get(chat_id, False):
                break
            try:
                await bot.send_message(
                    chat_id,
                    spam_text,
                    entities=shifted_entities if shifted_entities else None,
                    business_connection_id=message.business_connection_id,
                )
                await asyncio.sleep(0.35)
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 0.5)
            except Exception as e:
                logging.error(f"Ошибка спама: {e}")
                break
    finally:
        spam_running[chat_id] = False


async def cmd_stop(message: Message, bot: Bot):
    chat_id = message.chat.id
    await delete_command(message, bot)
    if spam_running.get(chat_id, False):
        spam_running[chat_id] = False
        try:
            await bot.send_message(
                chat_id,
                "⛔ Спам остановлен.",
                business_connection_id=message.business_connection_id,
            )
        except Exception as e:
            logging.warning(f"Ошибка /stop: {e}")
    else:
        try:
            await bot.send_message(
                chat_id,
                "ℹ️ Нет активного спама.",
                business_connection_id=message.business_connection_id,
            )
        except Exception as e:
            logging.warning(f"Ошибка /stop: {e}")


async def cmd_fuck(message: Message, bot: Bot):
    sender_name = get_display_name(message.from_user)

    chat = message.chat
    if chat.id != (message.from_user.id if message.from_user else None):
        partner_name = get_display_name(chat)
    else:
        partner_name = "собеседника"

    await delete_command(message, bot)

    text = (
        f'<tg-emoji emoji-id="5368621528436973317">🔥</tg-emoji>| '
        f'{sender_name} жестко выебал(а) {partner_name}.'
    )
    await bot.send_message(
        message.chat.id,
        text,
        parse_mode="HTML",
        business_connection_id=message.business_connection_id,
    )
