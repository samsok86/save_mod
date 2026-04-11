import asyncio
import logging
import random
from aiogram import Bot
from aiogram.types import Message, ReactionTypeCustomEmoji
from aiogram.exceptions import TelegramRetryAfter
from fun import get_display_name, delete_command

mother_running: dict[int, bool] = {}
mother_active_chats: set[int] = set()

MOTHER_MESSAGES = [
    '<tg-emoji emoji-id="5211025120918785460">❤</tg-emoji>| уже ебу твою мать',
    '<tg-emoji emoji-id="5298937724168853193">❤</tg-emoji>|поплачь сын шлюхи',
    '<tg-emoji emoji-id="5211155151053675393">❤</tg-emoji>|кончил на еблет твоей мамаше',
    '<tg-emoji emoji-id="5427290021491151861">❤</tg-emoji>| ты сынок шлюхи',
    '<tg-emoji emoji-id="5467378958469207997">❤</tg-emoji>|ебал твою мать в позе 67',
]

MOTHER_REACTION_EMOJI = "5334574128680675663"


def _get_partner_display(message: Message) -> str:
    if message.reply_to_message and message.reply_to_message.from_user:
        partner = message.reply_to_message.from_user
        if partner.username:
            return f"@{partner.username}"
        return get_display_name(partner)
    chat = message.chat
    if getattr(chat, "username", None):
        return f"@{chat.username}"
    return get_display_name(chat)


async def cmd_kick(message: Message, bot: Bot):
    partner_display = _get_partner_display(message)
    await delete_command(message, bot)
    text = (
        f'<tg-emoji emoji-id="5235731477907390413">👢</tg-emoji>| '
        f'отпинал мразь {partner_display}'
    )
    await bot.send_message(
        message.chat.id,
        text,
        parse_mode="HTML",
        business_connection_id=message.business_connection_id,
    )


async def cmd_shot(message: Message, bot: Bot):
    partner_display = _get_partner_display(message)
    await delete_command(message, bot)
    text = (
        f'<tg-emoji emoji-id="5880001689276124418">🔫</tg-emoji>| '
        f'расстрелял {partner_display}'
    )
    await bot.send_message(
        message.chat.id,
        text,
        parse_mode="HTML",
        business_connection_id=message.business_connection_id,
    )


async def cmd_id(message: Message, bot: Bot):
    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
    else:
        user = message.from_user

    await delete_command(message, bot)

    uid = user.id if user else "—"
    username = f"@{user.username}" if (user and user.username) else "—"

    text = (
        f'<tg-emoji emoji-id="5904630315946611415">👤</tg-emoji> '
        f'<b>{username}</b> | <code>{uid}</code>'
    )
    await bot.send_message(
        message.chat.id,
        text,
        parse_mode="HTML",
        business_connection_id=message.business_connection_id,
    )


async def cmd_mother(message: Message, bot: Bot):
    chat_id = message.chat.id

    if mother_running.get(chat_id, False):
        try:
            await bot.send_message(
                chat_id,
                "⏳ Уже запущено. Используйте /stop для остановки.",
                business_connection_id=message.business_connection_id,
            )
        except Exception:
            pass
        return

    await delete_command(message, bot)

    mother_running[chat_id] = True
    mother_active_chats.add(chat_id)

    try:
        for _ in range(100):
            if not mother_running.get(chat_id, False):
                break
            try:
                text = random.choice(MOTHER_MESSAGES)
                await bot.send_message(
                    chat_id,
                    text,
                    parse_mode="HTML",
                    business_connection_id=message.business_connection_id,
                )
                await asyncio.sleep(0.35)
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 0.5)
            except Exception as e:
                logging.error(f"Ошибка /mother: {e}")
                break
    finally:
        mother_running[chat_id] = False
        mother_active_chats.discard(chat_id)


async def set_mother_reaction(bot: Bot, message: Message):
    try:
        await bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[ReactionTypeCustomEmoji(custom_emoji_id=MOTHER_REACTION_EMOJI)],
            business_connection_id=message.business_connection_id,
        )
    except Exception as e:
        logging.warning(f"Ошибка реакции /mother: {e}")


COMMANDS_TEXT = (
    "<b>📋 Список команд:</b>\n\n"
    "<b>Общие:</b>\n"
    "/start — приветствие и инструкция подключения\n"
    "/commands — показать этот список\n\n"
    "<b>В бизнес-переписках:</b>\n"
    "/spam [кол-во] [текст] — отправить сообщение N раз (1–99)\n"
    "/stop — остановить спам\n"
    "/like — включить режим лайкера\n"
    "/nolike — выключить режим лайкера\n"
    "/save — скачать медиа по ссылке из соцсети\n"
    "/fuck — шуточная команда\n"
    "/kick — шуточная команда\n"
    "/shot — шуточная команда\n"
    "/id — показать ID и @username собеседника"
)


async def cmd_commands(message: Message):
    await message.answer(COMMANDS_TEXT, parse_mode="HTML")
