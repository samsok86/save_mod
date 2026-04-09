import asyncio
import logging
import os
import re
import shutil
import tempfile
from aiogram import Bot
from aiogram.types import Message, InputMediaPhoto, InputMediaVideo, FSInputFile

LOADING_TEXT = '<tg-emoji emoji-id="5443127283898405358">⏳</tg-emoji>Загружаю…'

MAX_FILE_SIZE = 49 * 1024 * 1024  # 49 MB

URL_PATTERN = re.compile(
    r'https?://(?:www\.)?'
    r'(?:tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com'
    r'|instagram\.com|instagr\.am'
    r'|youtube\.com|youtu\.be'
    r'|vk\.com|vkvideo\.ru'
    r'|twitter\.com|x\.com'
    r'|facebook\.com|fb\.com|fb\.watch'
    r'|reddit\.com|redd\.it'
    r'|pinterest\.com|pin\.it'
    r'|snapchat\.com'
    r'|twitch\.tv'
    r'|dailymotion\.com'
    r'|rumble\.com'
    r')[^\s<>"\']+'
)


def extract_url(text: str) -> str | None:
    match = URL_PATTERN.search(text)
    if match:
        return match.group(0).rstrip('.,;!?)')
    return None


def is_image(path: str) -> bool:
    return path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))


def is_video(path: str) -> bool:
    return path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'))


def get_valid_files(tmpdir: str) -> list[str]:
    result = []
    for f in sorted(os.listdir(tmpdir)):
        full = os.path.join(tmpdir, f)
        if not os.path.isfile(full):
            continue
        if not (is_image(f) or is_video(f)):
            continue
        if os.path.getsize(full) > MAX_FILE_SIZE:
            logging.warning(f"Файл слишком большой, пропускаем: {f}")
            continue
        result.append(full)
    return result


async def download_media(url: str) -> tuple[list[str], str]:
    tmpdir = tempfile.mkdtemp()
    ydl_opts = {
        'outtmpl': os.path.join(tmpdir, '%(autonumber)03d.%(ext)s'),
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'noplaylist': False,
        'max_filesize': MAX_FILE_SIZE,
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        },
        'extractor_args': {
            'tiktok': {'webpage_download': True},
        },
    }

    loop = asyncio.get_event_loop()

    def _download():
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            logging.error(f"yt-dlp ошибка: {e}")

    await loop.run_in_executor(None, _download)
    files = get_valid_files(tmpdir)
    return files, tmpdir


async def cmd_save(message: Message, bot: Bot):
    url = None

    if message.reply_to_message:
        src_text = (
            message.reply_to_message.text
            or message.reply_to_message.caption
            or ""
        )
        url = extract_url(src_text)

    if not url:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) > 1:
            url = extract_url(parts[1])

    if not url:
        try:
            await bot.delete_messages(
                chat_id=message.chat.id,
                message_ids=[message.message_id],
                business_connection_id=message.business_connection_id,
            )
        except Exception:
            pass
        try:
            await bot.send_message(
                message.chat.id,
                "❌ Ссылка не найдена. Ответь командой /save на сообщение со ссылкой.",
                business_connection_id=message.business_connection_id,
            )
        except Exception:
            pass
        return

    loading_msg_id = message.message_id
    try:
        await bot.edit_message_text(
            text=LOADING_TEXT,
            chat_id=message.chat.id,
            message_id=loading_msg_id,
            business_connection_id=message.business_connection_id,
            parse_mode="HTML",
        )
    except Exception as e:
        logging.warning(f"Не удалось показать загрузку: {e}")

    files, tmpdir = await download_media(url)

    if not files:
        try:
            await bot.edit_message_text(
                text="❌ Не удалось скачать медиа по этой ссылке.",
                chat_id=message.chat.id,
                message_id=loading_msg_id,
                business_connection_id=message.business_connection_id,
            )
        except Exception:
            pass
        shutil.rmtree(tmpdir, ignore_errors=True)
        return

    try:
        await bot.delete_messages(
            chat_id=message.chat.id,
            message_ids=[loading_msg_id],
            business_connection_id=message.business_connection_id,
        )
    except Exception as e:
        logging.warning(f"Не удалось удалить сообщение загрузки: {e}")

    try:
        if len(files) == 1:
            f = files[0]
            if is_video(f):
                await bot.send_video(
                    message.chat.id,
                    FSInputFile(f),
                    business_connection_id=message.business_connection_id,
                )
            else:
                await bot.send_photo(
                    message.chat.id,
                    FSInputFile(f),
                    business_connection_id=message.business_connection_id,
                )
        else:
            chunks = [files[i:i + 10] for i in range(0, len(files), 10)]
            for chunk in chunks:
                media = []
                for f in chunk:
                    if is_video(f):
                        media.append(InputMediaVideo(media=FSInputFile(f)))
                    else:
                        media.append(InputMediaPhoto(media=FSInputFile(f)))
                await bot.send_media_group(
                    message.chat.id,
                    media=media,
                    business_connection_id=message.business_connection_id,
                )
                await asyncio.sleep(0.5)
    except Exception as e:
        logging.error(f"Ошибка отправки медиа: {e}")
        try:
            await bot.send_message(
                message.chat.id,
                "❌ Не удалось отправить медиафайл.",
                business_connection_id=message.business_connection_id,
            )
        except Exception:
            pass
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


async def cmd_broadcast(message: Message, bot: Bot, connected_users: dict):
    reply = message.reply_to_message
    broadcast_text = None

    if not reply:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await message.answer(
                "Использование:\n"
                "• /broadcast <текст> — разослать текст\n"
                "• Ответь на сообщение командой /broadcast — разослать то сообщение"
            )
            return
        broadcast_text = parts[1]

    if not connected_users:
        await message.answer("👥 Нет подключённых пользователей для рассылки.")
        return

    success = 0
    fail = 0

    for uid in list(connected_users.keys()):
        try:
            if reply:
                await bot.copy_message(
                    chat_id=uid,
                    from_chat_id=reply.chat.id,
                    message_id=reply.message_id,
                )
            else:
                await bot.send_message(uid, broadcast_text)
            success += 1
        except Exception as e:
            logging.warning(f"Ошибка рассылки пользователю {uid}: {e}")
            fail += 1
        await asyncio.sleep(0.05)

    await message.answer(
        f"✅ Рассылка завершена:\n"
        f"✓ Доставлено: {success}\n"
        f"✗ Ошибок: {fail}"
    )
