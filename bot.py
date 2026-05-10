import os
import asyncio
import logging
import re
import yt_dlp

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "/tmp/yt_downloads")
PROXY_URL = os.getenv("PROXY_URL", "socks5://127.0.0.1:10808")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

session = AiohttpSession(proxy=PROXY_URL)
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher()

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

YOUTUBE_REGEX = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)"
    r"[\w\-]+"
)


def is_youtube_url(text: str) -> bool:
    return bool(YOUTUBE_REGEX.search(text))


def get_video_info(url: str) -> dict:
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info


def build_format_keyboard(url: str, info: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    # MP3 audio
    builder.button(
        text="🎵 MP3 (аудио)",
        callback_data=f"dl:mp3:best:{url}"
    )

    # MP4 variants — собираем уникальные высоты
    seen = set()
    formats = info.get("formats", [])
    video_formats = []
    for f in formats:
        if f.get("vcodec") != "none" and f.get("acodec") != "none":
            h = f.get("height")
            if h and h not in seen:
                seen.add(h)
                video_formats.append(h)

    # Если нет форматов с обоими кодеками — добавляем стандартные
    if not video_formats:
        video_formats = [1080, 720, 480, 360]

    for h in sorted(video_formats, reverse=True)[:4]:
        builder.button(
            text=f"🎬 MP4 {h}p",
            callback_data=f"dl:mp4:{h}:{url}"
        )

    builder.adjust(1)
    return builder.as_markup()


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Отправь мне ссылку на YouTube видео, "
        "и я предложу варианты для скачивания."
    )


@dp.message(F.text)
async def handle_message(message: types.Message):
    text = message.text.strip()

    if not is_youtube_url(text):
        await message.answer("Это не похоже на ссылку YouTube. Попробуй ещё раз.")
        return

    status_msg = await message.answer("⏳ Получаю информацию о видео...")

    try:
        info = await asyncio.get_event_loop().run_in_executor(
            None, get_video_info, text
        )
    except Exception as e:
        logger.error(f"Error fetching video info: {e}")
        await status_msg.edit_text("❌ Не удалось получить информацию о видео. Проверь ссылку.")
        return

    title = info.get("title", "Видео")
    duration = info.get("duration", 0)
    mins, secs = divmod(duration, 60)

    keyboard = build_format_keyboard(text, info)

    await status_msg.edit_text(
        f"📹 <b>{title}</b>\n"
        f"⏱ Длительность: {mins}:{secs:02d}\n\n"
        f"Выбери формат для скачивания:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("dl:"))
async def handle_download(callback: types.CallbackQuery):
    await callback.answer("Начинаю загрузку...")

    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.message.edit_text("❌ Ошибка формата запроса.")
        return

    _, fmt, quality, url = parts

    status_msg = await callback.message.edit_text("⬇️ Скачиваю, подожди...")

    try:
        file_path = await asyncio.get_event_loop().run_in_executor(
            None, download_media, url, fmt, quality
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status_msg.edit_text("❌ Ошибка при скачивании. Попробуй другой формат или позже.")
        return

    await status_msg.edit_text("📤 Загружаю файл в Telegram...")

    try:
        input_file = FSInputFile(file_path)
        if fmt == "mp3":
            await callback.message.answer_audio(input_file)
        else:
            await callback.message.answer_video(input_file)
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Send error: {e}")
        await status_msg.edit_text(
            "❌ Файл слишком большой для отправки через Telegram (лимит 50 МБ). "
            "Попробуй формат с меньшим качеством."
        )
    finally:
        # Удаляем файл после отправки
        if os.path.exists(file_path):
            os.remove(file_path)


def download_media(url: str, fmt: str, quality: str) -> str:
    if fmt == "mp3":
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
        }
    else:
        height = quality
        ydl_opts = {
            "format": f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best[height<={height}]",
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True,
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)

        # Для mp3 расширение меняется после постпроцессинга
        if fmt == "mp3":
            base = os.path.splitext(file_path)[0]
            file_path = base + ".mp3"

    return file_path


async def main():
    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
