"""
会議室予約Bot - Botモーダル版
メンションでモーダルフォームを表示して予約・キャンセルを行う
"""
import logging
import re
import threading
import time
from datetime import datetime

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ログ設定（接続状態の監視用）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from config import (
    SLACK_BOT_TOKEN,
    SLACK_SIGNING_SECRET,
    SLACK_APP_TOKEN,
    REMINDER_OPTIONS,
)
from database import (
    init_db,
    create_reservation,
    get_reservations_by_date,
    get_reservations_by_user,
    delete_reservation,
    check_conflict,
    get_pending_reminders,
    mark_reminder_sent,
)

app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)


# ====================
# ユーティリティ関数
# ====================

def format_reminder_text(minutes: int) -> str:
    """リマインダー分数を表示用テキストに変換"""
    for text, mins in REMINDER_OPTIONS.items():
        if mins == minutes:
            return text
    return f"{minutes}分前"


# キャッシュ用変数（起動時に一度だけ生成）
_TIME_OPTIONS = None
_REMINDER_OPTIONS = None


def generate_time_options():
    """時刻選択用のオプションを生成（30分刻み）- キャッシュ"""
    global _TIME_OPTIONS
    if _TIME_OPTIONS is None:
        _TIME_OPTIONS = []
        for hour in range(7, 22):
            for minute in [0, 30]:
                time_str = f"{hour:02d}:{minute:02d}"
                _TIME_OPTIONS.append({
                    "text": {"type": "plain_text", "text": time_str},
                    "value": time_str
                })
    return _TIME_OPTIONS


def generate_reminder_options():
    """リマインダー選択用のオプションを生成 - キャッシュ"""
    global _REMINDER_OPTIONS
    if _REMINDER_OPTIONS is None:
        _REMINDER_OPTIONS = []
        for text, minutes in REMINDER_OPTIONS.items():
            _REMINDER_OPTIONS.append({
                "text": {"type": "plain_text", "text": text},
                "value": str(minutes)
            })
    return _REMINDER_OPTIONS


# ====================
# メンション処理
# ====================

@app.event("app_mention")
def handle_app_mention(body, client, event, say):
    """メンションを処理してモーダルを開く"""
    text = event["text"]
    user_id = event["user"]

    print(f"[DEBUG] Received mention: {repr(text)}")

    # Botへのメンション部分を除去（大文字小文字両対応）
    text = re.sub(r"<@[A-Za-z0-9]+>", "", text).strip()

    print(f"[DEBUG] After cleanup: {repr(text)}")

    if text.startswith("予約"):
        # ボタン付きメッセージを送信
        say(
            text="予約フォームを開くには下のボタンをクリックしてください",
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "会議室を予約するには、下のボタンをクリックしてください。"}
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "予約フォームを開く"},
                            "style": "primary",
                            "action_id": "open_reservation_modal"
                        }
                    ]
                }
            ]
        )
    elif text.startswith("キャンセル"):
        # キャンセル用のボタンを送信
        reservations = get_reservations_by_user(user_id)
        if not reservations:
            say("キャンセルできる予約がありません。")
            return

        say(
            text="キャンセルする予約を選択してください",
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "キャンセルする予約を選択してください。"}
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "キャンセルフォームを開く"},
                            "style": "danger",
                            "action_id": "open_cancel_modal"
                        }
                    ]
                }
            ]
        )
    elif text.startswith("確認"):
        handle_check(text, say)
    elif text.startswith("ヘルプ") or text.startswith("help"):
        handle_help(say)
    else:
        handle_help(say)


# ====================
# 予約モーダル
# ====================

@app.action("open_reservation_modal")
def handle_open_reservation_modal(ack, body, client):
    """予約モーダルを開くボタンのアクション"""
    ack()

    user_id = body["user"]["id"]
    today = datetime.now().strftime("%Y-%m-%d")

    modal = {
        "type": "modal",
        "callback_id": "reservation_modal",
        "title": {"type": "plain_text", "text": "会議室予約"},
        "submit": {"type": "plain_text", "text": "予約する"},
        "close": {"type": "plain_text", "text": "キャンセル"},
        "blocks": [
            {
                "type": "input",
                "block_id": "channel_block",
                "label": {"type": "plain_text", "text": "対象チャンネル"},
                "element": {
                    "type": "conversations_select",
                    "action_id": "channel_select",
                    "placeholder": {"type": "plain_text", "text": "チャンネルを選択"},
                    "filter": {
                        "include": ["public", "private"],
                        "exclude_bot_users": True
                    }
                }
            },
            {
                "type": "input",
                "block_id": "date_block",
                "label": {"type": "plain_text", "text": "予約日"},
                "element": {
                    "type": "datepicker",
                    "action_id": "date_select",
                    "initial_date": today,
                    "placeholder": {"type": "plain_text", "text": "日付を選択"}
                }
            },
            {
                "type": "input",
                "block_id": "start_time_block",
                "label": {"type": "plain_text", "text": "開始時間"},
                "element": {
                    "type": "static_select",
                    "action_id": "start_time_select",
                    "placeholder": {"type": "plain_text", "text": "開始時間を選択"},
                    "options": generate_time_options()
                }
            },
            {
                "type": "input",
                "block_id": "end_time_block",
                "label": {"type": "plain_text", "text": "終了時間"},
                "element": {
                    "type": "static_select",
                    "action_id": "end_time_select",
                    "placeholder": {"type": "plain_text", "text": "終了時間を選択"},
                    "options": generate_time_options()
                }
            },
            {
                "type": "input",
                "block_id": "event_name_block",
                "label": {"type": "plain_text", "text": "ミーティング名"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "event_name_input",
                    "placeholder": {"type": "plain_text", "text": "例: 週次定例会議"}
                }
            },
            {
                "type": "input",
                "block_id": "reminder_block",
                "label": {"type": "plain_text", "text": "リマインダー"},
                "element": {
                    "type": "static_select",
                    "action_id": "reminder_select",
                    "placeholder": {"type": "plain_text", "text": "通知タイミングを選択"},
                    "options": generate_reminder_options(),
                    "initial_option": {
                        "text": {"type": "plain_text", "text": "15分前"},
                        "value": "15"
                    }
                }
            }
        ],
        "private_metadata": user_id
    }

    client.views_open(trigger_id=body["trigger_id"], view=modal)


@app.view("reservation_modal")
def handle_reservation_submission(ack, body, client, view):
    """予約モーダルの送信処理"""
    user_id = body["user"]["id"]

    # ユーザー情報を取得
    user_info = client.users_info(user=user_id)
    user_name = user_info["user"]["real_name"] or user_info["user"]["name"]

    # フォームの値を取得
    values = view["state"]["values"]

    channel_id = values["channel_block"]["channel_select"]["selected_conversation"]
    date_str = values["date_block"]["date_select"]["selected_date"]
    start_time_str = values["start_time_block"]["start_time_select"]["selected_option"]["value"]
    end_time_str = values["end_time_block"]["end_time_select"]["selected_option"]["value"]
    event_name = values["event_name_block"]["event_name_input"]["value"]
    reminder_minutes = int(values["reminder_block"]["reminder_select"]["selected_option"]["value"])

    # 日時のパース
    start_dt = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime(f"{date_str} {end_time_str}", "%Y-%m-%d %H:%M")

    # バリデーション
    errors = {}

    if end_dt <= start_dt:
        errors["end_time_block"] = "終了時間は開始時間より後に設定してください"

    if start_dt < datetime.now():
        errors["date_block"] = "過去の日時は予約できません"

    # 重複チェック
    conflict = check_conflict(start_dt, end_dt)
    if conflict:
        conflict_start = datetime.fromisoformat(conflict["start_time"])
        conflict_end = datetime.fromisoformat(conflict["end_time"])
        errors["start_time_block"] = f"その時間帯は既に予約があります（{conflict['event_name']} / {conflict_start.strftime('%H:%M')}-{conflict_end.strftime('%H:%M')}）"

    if errors:
        ack(response_action="errors", errors=errors)
        return

    ack()

    # 予約を作成
    reservation_id = create_reservation(
        user_id=user_id,
        user_name=user_name,
        channel_id=channel_id,
        event_name=event_name,
        start_time=start_dt,
        end_time=end_dt,
        reminder_minutes=reminder_minutes
    )

    # 予約完了メッセージ
    message = (
        f"新しい予約が作成されました\n\n"
        f"*予約ID:* {reservation_id}\n"
        f"*予約者:* {user_name}\n"
        f"*日時:* {start_dt.strftime('%Y/%m/%d %H:%M')} - {end_dt.strftime('%H:%M')}\n"
        f"*ミーティング名:* {event_name}\n"
        f"*リマインド:* {format_reminder_text(reminder_minutes)}"
    )

    # 対象チャンネルに通知
    client.chat_postMessage(
        channel=channel_id,
        text=message
    )


# ====================
# キャンセルモーダル
# ====================

@app.action("open_cancel_modal")
def handle_open_cancel_modal(ack, body, client):
    """キャンセルモーダルを開くボタンのアクション"""
    ack()

    user_id = body["user"]["id"]
    reservations = get_reservations_by_user(user_id)

    if not reservations:
        client.chat_postMessage(
            channel=user_id,
            text="キャンセルできる予約がありません。"
        )
        return

    # 予約一覧をオプションとして生成
    options = []
    for r in reservations:
        start = datetime.fromisoformat(r["start_time"])
        label = f"{start.strftime('%m/%d %H:%M')} - {r['event_name']}"
        if len(label) > 75:
            label = label[:72] + "..."
        options.append({
            "text": {"type": "plain_text", "text": label},
            "value": str(r["id"])
        })

    modal = {
        "type": "modal",
        "callback_id": "cancel_modal",
        "title": {"type": "plain_text", "text": "予約キャンセル"},
        "submit": {"type": "plain_text", "text": "キャンセルする"},
        "close": {"type": "plain_text", "text": "閉じる"},
        "blocks": [
            {
                "type": "input",
                "block_id": "reservation_block",
                "label": {"type": "plain_text", "text": "キャンセルする予約を選択"},
                "element": {
                    "type": "static_select",
                    "action_id": "reservation_select",
                    "placeholder": {"type": "plain_text", "text": "予約を選択"},
                    "options": options
                }
            }
        ],
        "private_metadata": user_id
    }

    client.views_open(trigger_id=body["trigger_id"], view=modal)


@app.view("cancel_modal")
def handle_cancel_submission(ack, body, client, view):
    """キャンセルモーダルの送信処理"""
    ack()

    user_id = body["user"]["id"]
    values = view["state"]["values"]
    reservation_id = int(values["reservation_block"]["reservation_select"]["selected_option"]["value"])

    # 予約を削除
    deleted = delete_reservation(reservation_id, user_id)

    if deleted:
        start = datetime.fromisoformat(deleted["start_time"])
        message = (
            f"予約がキャンセルされました\n\n"
            f"*予約ID:* {deleted['id']}\n"
            f"*キャンセル者:* <@{user_id}>\n"
            f"*日時:* {start.strftime('%Y/%m/%d %H:%M')}\n"
            f"*ミーティング名:* {deleted['event_name']}"
        )

        # 対象チャンネルに通知
        client.chat_postMessage(
            channel=deleted["channel_id"],
            text=message
        )
    else:
        client.chat_postMessage(
            channel=user_id,
            text="予約のキャンセルに失敗しました。"
        )


# ====================
# 確認・ヘルプ
# ====================

def handle_check(text: str, say):
    """予約確認を処理"""
    try:
        # 日付を抽出
        pattern = r"確認\s*(\d{1,4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[/-]\d{1,2})?"
        match = re.match(pattern, text)

        if match and match.group(1):
            date_str = match.group(1).replace("-", "/")
            if date_str.count("/") == 1:
                date_str = f"{datetime.now().year}/{date_str}"
            date_parts = date_str.split("/")
            target_date = datetime(int(date_parts[0]), int(date_parts[1]), int(date_parts[2]))
        else:
            target_date = datetime.now()

        date_formatted = target_date.strftime("%Y-%m-%d")
        reservations = get_reservations_by_date(date_formatted)

        if not reservations:
            say(f"{target_date.strftime('%Y/%m/%d')} の予約はありません。")
            return

        lines = [f"*{target_date.strftime('%Y/%m/%d')} の予約一覧*\n"]
        for r in reservations:
            start = datetime.fromisoformat(r["start_time"])
            end = datetime.fromisoformat(r["end_time"])
            lines.append(
                f"*[ID: {r['id']}]* {start.strftime('%H:%M')} - {end.strftime('%H:%M')}\n"
                f"  {r['event_name']} / {r['user_name']}\n"
                f"  対象: <#{r['channel_id']}>"
            )
            lines.append("")

        say("\n".join(lines))

    except Exception as e:
        say(f"予約の確認中にエラーが発生しました: {str(e)}")


def handle_help(say):
    """ヘルプメッセージを表示"""
    say(
        "*会議室予約Bot ヘルプ*\n\n"
        "*予約する:*\n"
        "`@reserve-bot 予約` → ボタンをクリックしてフォームを開く\n\n"
        "*予約をキャンセル:*\n"
        "`@reserve-bot キャンセル` → 自分の予約一覧から選択\n\n"
        "*予約を確認:*\n"
        "`@reserve-bot 確認` (今日の予約)\n"
        "`@reserve-bot 確認 2025/01/15` (指定日の予約)\n\n"
        "*ヘルプ:*\n"
        "`@reserve-bot ヘルプ`"
    )


# ====================
# リマインダー機能
# ====================

def send_reminders():
    """未送信のリマインダーをチェックして送信"""
    reminders = get_pending_reminders()
    if not reminders:
        return

    client = app.client  # Boltアプリのクライアントを使用

    for r in reminders:
        try:
            start = datetime.fromisoformat(r["start_time"])
            message = (
                f"リマインダー: まもなく会議が始まります\n\n"
                f"*ミーティング名:* {r['event_name']}\n"
                f"*時間:* {start.strftime('%Y/%m/%d %H:%M')}\n"
                f"*予約者:* {r['user_name']}"
            )
            client.chat_postMessage(
                channel=r["channel_id"],
                text=message
            )
            mark_reminder_sent(r["id"])
            print(f"Reminder sent for reservation {r['id']}")
        except Exception as e:
            print(f"Failed to send reminder for {r['id']}: {e}")


def reminder_loop():
    """リマインダーを定期的にチェックするループ"""
    while True:
        try:
            send_reminders()
        except Exception as e:
            print(f"Reminder loop error: {e}")
        time.sleep(30)  # 30秒ごとにチェック


# ====================
# メイン
# ====================

def main():
    """メインエントリーポイント"""
    init_db()
    print("Database initialized.")

    # リマインダースレッドを開始
    reminder_thread = threading.Thread(target=reminder_loop, daemon=True)
    reminder_thread.start()
    print("Reminder scheduler started.")

    # Socket Mode接続（自動再接続付き）
    while True:
        try:
            handler = SocketModeHandler(app, SLACK_APP_TOKEN)
            print("Bot is running... (Socket Mode)")
            handler.start()
        except KeyboardInterrupt:
            print("Bot stopped by user.")
            break
        except Exception as e:
            print(f"Connection error: {e}")
            print("Reconnecting in 5 seconds...")
            time.sleep(5)


if __name__ == "__main__":
    main()
