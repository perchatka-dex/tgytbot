# YouTube Downloader Bot

Телеграм бот для скачивания видео и аудио с YouTube.

## Что умеет

- Принимает ссылки на YouTube видео (включая Shorts)
- Показывает доступные форматы: MP3 и MP4 в разных качествах (360p, 480p, 720p, 1080p)
- Скачивает и отправляет файл прямо в чат

## Структура проекта

```
.
├── bot.py              # Основной код бота
├── requirements.txt    # Python зависимости
├── .env.example        # Пример конфига
├── Dockerfile
└── docker-compose.yml
```

## Запуск на Ubuntu сервере через Docker (рекомендуется)

### 1. Установи Docker и Docker Compose

```bash
sudo apt update
sudo apt install -y docker.io docker-compose
sudo systemctl enable --now docker
```

### 2. Создай бота в Telegram

Напиши [@BotFather](https://t.me/BotFather), создай бота командой `/newbot`, получи токен.

### 3. Залей файлы на сервер

С локальной машины (или через git):

```bash
scp -r "F:\tg bot skachka" user@your-server-ip:/home/user/yt-bot
```

Или через git:

```bash
# На локальной машине
cd "F:\tg bot skachka"
git init
git add .
git commit -m "init"
git remote add origin https://github.com/yourname/yt-bot.git
git push -u origin main

# На сервере
git clone https://github.com/yourname/yt-bot.git
cd yt-bot
```

### 4. Создай .env файл на сервере

```bash
cd /home/user/yt-bot
cp .env.example .env
nano .env
```

Вставь свой токен:

```
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
DOWNLOAD_DIR=/tmp/yt_downloads
```

### 5. Запусти бота

```bash
docker-compose up -d --build
```

### Полезные команды

```bash
# Посмотреть логи
docker-compose logs -f

# Остановить
docker-compose down

# Перезапустить после изменений
docker-compose up -d --build
```

## Запуск без Docker (напрямую на сервере)

```bash
# Установи зависимости системы
sudo apt update
sudo apt install -y python3 python3-pip ffmpeg

# Установи Python зависимости
pip3 install -r requirements.txt

# Создай .env
cp .env.example .env
nano .env  # вставь токен

# Запусти
python3 bot.py
```

Чтобы бот работал в фоне после закрытия терминала:

```bash
nohup python3 bot.py > bot.log 2>&1 &
```

Или через systemd — создай файл `/etc/systemd/system/yt-bot.service`:

```ini
[Unit]
Description=YouTube Downloader Bot
After=network.target

[Service]
WorkingDirectory=/home/user/yt-bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
EnvironmentFile=/home/user/yt-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now yt-bot
sudo journalctl -u yt-bot -f  # логи
```

## Ограничения

- Telegram ограничивает размер файлов до **50 МБ** для ботов. Длинные видео в высоком качестве могут не отправиться — бот сообщит об этом и предложит выбрать меньшее качество.
- yt-dlp периодически нужно обновлять, если YouTube меняет API: `pip3 install -U yt-dlp` или пересобери Docker образ.
