import asyncio
import logging
import random
from aiogram import Bot
from aiogram.types import Message, MessageEntity


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


# =========================
# 🔥 /spam
# =========================
async def cmd_spam(message: Message, bot: Bot):
    raw = message.text or ""
    parts = raw.split(maxsplit=2)

    if len(parts) < 3:
        await bot.send_message(
            message.chat.id,
            "❌ Использование: /spam [кол-во 1–99] [текст до 200 символов]",
            business_connection_id=message.business_connection_id,
            reply_to_message_id=message.message_id,
        )
        return

    if not parts[1].isdigit():
        await bot.send_message(
            message.chat.id,
            "❌ Количество должно быть числом от 1 до 99",
            business_connection_id=message.business_connection_id,
            reply_to_message_id=message.message_id,
        )
        return

    count = max(1, min(int(parts[1]), 99))
    spam_text = parts[2]

    if len(spam_text) > 200:
        await bot.send_message(
            message.chat.id,
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


# =========================
# 🔥 /fuck (исправленная версия)
# =========================
async def cmd_fuck(message: Message, bot: Bot):
    sender_name = get_display_name(message.from_user)

    # 👉 Определяем цель
    if message.reply_to_message and message.reply_to_message.from_user:
        partner = message.reply_to_message.from_user
        partner_name = get_display_name(partner)
        is_reply = True
    else:
        partner_name = "сам себя 💀"
        is_reply = False

    text = (
        f'<tg-emoji emoji-id="5368621528436973317">🔥</tg-emoji> | '
        f'<b>{sender_name}</b> жестко выебал(а) <b>{partner_name}</b>'
    )

    # 👉 Если reply — редактируем сообщение
    if is_reply:
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=message.chat.id,
                message_id=message.message_id,
                parse_mode="HTML",
                business_connection_id=message.business_connection_id,
            )
        except Exception as e:
            logging.warning(f"Не удалось отредактировать: {e}")

            # fallback 👉 если не получилось — отправляем новое
            await bot.send_message(
                message.chat.id,
                text,
                parse_mode="HTML",
                business_connection_id=message.business_connection_id,
            )
    else:
        # 👉 Если не reply — удаляем и отправляем новое
        await delete_command(message, bot)

        await bot.send_message(
            message.chat.id,
            text,
            parse_mode="HTML",
            business_connection_id=message.business_connection_id,
        )
