import asyncio
import logging
from aiogram import Router, Bot
from aiogram.types import Message, MessageEntity
from aiogram.filters import Command

router = Router()


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


async def delete_command(message: Message, bot: Bot):
    try:
        await bot.delete_messages(
            chat_id=message.chat.id,
            message_ids=[message.message_id],
            business_connection_id=message.business_connection_id,
        )
    except Exception as e:
        logging.warning(f"Не удалось удалить команду: {e}")


async def reply_in_chat(message: Message, bot: Bot, text: str, parse_mode: str = "HTML"):
    await bot.send_message(
        message.chat.id,
        text,
        parse_mode=parse_mode,
        business_connection_id=message.business_connection_id,
        reply_to_message_id=message.message_id,
    )


async def send_in_chat(message: Message, bot: Bot, text: str, parse_mode: str = "HTML"):
    await bot.send_message(
        message.chat.id,
        text,
        parse_mode=parse_mode,
        business_connection_id=message.business_connection_id,
    )


@router.business_message(Command("spam"))
async def cmd_spam(message: Message, bot: Bot):
    raw = message.text or ""
    parts = raw.split(maxsplit=2)
    if len(parts) < 3:
        await reply_in_chat(message, bot, "❌ Использование: /spam [кол-во 1–99] [текст до 200 символов]")
        return
    if not parts[1].isdigit():
        await reply_in_chat(message, bot, "❌ Количество должно быть числом от 1 до 99")
        return
    count = max(1, min(int(parts[1]), 99))
    spam_text = parts[2]
    if len(spam_text) > 200:
        await reply_in_chat(message, bot, "❌ Текст не должен превышать 200 символов")
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
    for _ in range(count):
        try:
            await bot.send_message(
                message.chat.id,
                spam_text,
                entities=shifted_entities if shifted_entities else None,
                business_connection_id=message.business_connection_id,
            )
            await asyncio.sleep(0.35)
        except Exception as e:
            logging.error(f"Ошибка спама: {e}")
            break


@router.business_message(Command("fuck"))
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
    await send_in_chat(message, bot, text)
