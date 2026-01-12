# 会議室予約システム（Botモーダル版）

Slack Botのモーダル機能を使って会議室の予約・キャンセル・確認ができるシステムです。

## 機能

| コマンド | 動作 |
|----------|------|
| `@reserve-bot 予約` | 予約フォーム（モーダル）を表示 |
| `@reserve-bot キャンセル` | 自分の予約一覧から選択して削除 |
| `@reserve-bot 確認` | 今日の予約一覧を表示 |
| `@reserve-bot 確認 2025/01/15` | 指定日の予約一覧を表示 |
| `@reserve-bot ヘルプ` | 使い方を表示 |

---

## セットアップ

### 1. Slack Appの作成

[Slack API](https://api.slack.com/apps) で「Create New App」→「From manifest」を選択し、以下のYAMLを貼り付け:

```yaml
display_information:
  name: 会議室予約くん
features:
  bot_user:
    display_name: reserve-bot
    always_online: true
oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - chat:write
      - users:read
      - channels:read
      - im:write
settings:
  event_subscriptions:
    bot_events:
      - app_mention
  interactivity:
    is_enabled: true
  org_deploy_enabled: false
  socket_mode_enabled: true
  token_rotation_enabled: false
```

### 2. トークンの取得

| 環境変数 | 取得場所 |
|----------|----------|
| `SLACK_BOT_TOKEN` | OAuth & Permissions → Bot User OAuth Token |
| `SLACK_SIGNING_SECRET` | Basic Information → Signing Secret |
| `SLACK_APP_TOKEN` | Basic Information → App-Level Tokens（スコープ: `connections:write`） |
| `RESERVATION_CHANNEL_ID` | 予約通知を投稿するチャンネルのID |

### 3. 環境変数の設定

```bash
cp .env.example .env
# .envを編集してトークンを設定
```

### 4. 依存関係のインストール

```bash
cd /path/to/meeting-room-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. 起動

```bash
cd src
python bot.py
```

---

## 使い方

### 1. Botをチャンネルに招待

```
/invite @reserve-bot
```

### 2. 予約する

```
@reserve-bot 予約
```

ボタンをクリックすると予約フォームが表示されます。

**入力項目:**
- 対象チャンネル（リマインド通知先）
- 予約日
- 開始時間・終了時間
- ミーティング名
- リマインダー（5分前〜3時間前）

### 3. 予約を確認

```
@reserve-bot 確認
@reserve-bot 確認 2025/01/15
```

### 4. 予約をキャンセル

```
@reserve-bot キャンセル
```

自分の予約一覧から選択してキャンセルできます。

---

## 通知

- **予約完了時**: 予約通知チャンネル + 予約者へDM
- **キャンセル時**: 予約通知チャンネル + 予約者へDM
- **リマインダー**: 対象チャンネルに通知（Phase 2で実装）

---

## ディレクトリ構成

```
meeting-room-bot/
├── src/
│   ├── bot.py          # メインBot処理（モーダル対応）
│   ├── database.py     # データベース操作
│   └── config.py       # 設定管理
├── data/
│   └── reservations.db # SQLiteデータベース（自動生成）
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## トラブルシューティング

### モーダルが表示されない

1. Slack App設定で「Interactivity & Shortcuts」が有効か確認
2. Socket Modeが有効か確認
3. `SLACK_APP_TOKEN`が正しく設定されているか確認

### Botが反応しない

1. Botがチャンネルに招待されているか確認
2. ターミナルでエラーが出ていないか確認
3. `SLACK_BOT_TOKEN`が正しいか確認
