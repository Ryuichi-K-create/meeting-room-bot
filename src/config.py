import os
from dotenv import load_dotenv

load_dotenv()

# Slack設定
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

# 予約通知用チャンネルID
RESERVATION_CHANNEL_ID = os.getenv("RESERVATION_CHANNEL_ID")

# データベース設定
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/reservations.db")

# サーバー設定
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 3000))

# リマインダー選択肢（分）
REMINDER_OPTIONS = {
    "5分前": 5,
    "10分前": 10,
    "15分前": 15,
    "30分前": 30,
    "1時間前": 60,
    "3時間前": 180,
    "24時間前": 1440,
}
