# Ribl Verify Bot

Discord公式OAuth2を使った「認証→ロール自動付与」Botです。
認証を試みたユーザーのDiscordユーザー名・ユーザーID・IPアドレスを、
管理者専用チャンネルに自動でログ送信します。

## 構成

```
ribl-verify-bot/
├── bot/                # Discord Bot (discord.py)
│   ├── bot.py
│   └── requirements.txt
├── website/            # 認証サイト (Flask, OAuth2コールバック処理)
│   ├── app.py
│   ├── templates/result.html
│   └── requirements.txt
├── shared/             # Bot/サイト共通のDBアクセス層 (SQLite)
│   └── db.py
├── data/                # SQLiteファイルの保存先 (.gitignore対象)
├── .env.example
└── .gitignore
```

## 仕組み

1. 管理者が `/verify-role add @role` で付与したいロールを登録
2. 管理者が `/verify-log-channel #admin-only` でログ送信先を設定(**必ず管理者専用チャンネルにすること**)
3. 管理者が `/verify-panel` を実行 → 「認証する」ボタン付きパネルが投稿される
4. ユーザーがボタンを押すと、認証サイトの `/login` → Discord公式の `discord.com/oauth2/authorize` にリダイレクト
5. ユーザーが許可すると `/callback` に戻り、サイトがアクセストークンとユーザー情報を取得し、リクエスト元IPアドレスを記録
6. サイトがBotの内部API (`/grant`, localhostのみ) を呼び出し、ロール付与とログ送信を実行

要求するOAuthスコープは `identify` のみです。メッセージの読み取り・送信権限などは一切要求しません。

## セットアップ

### 1. Discord Developer Portal で準備

- https://discord.com/developers/applications で新規アプリケーションを作成
- Bot タブで Bot を作成し、トークンを取得 (`DISCORD_BOT_TOKEN`)
  - Privileged Gateway Intents で **SERVER MEMBERS INTENT** を有効化
- OAuth2 タブで Client ID / Client Secret を取得
- OAuth2 → Redirects に `https://your-domain.example.com/callback` を登録
- Bot をサーバーに招待する際は `applications.commands` と `bot` スコープ、
  権限は **Manage Roles** のみで十分です

### 2. 環境変数の設定

```bash
cp .env.example .env
# .env を編集し、各値を埋める
```

### 3. Bot の起動

```bash
cd bot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python bot.py
```

### 4. 認証サイトの起動

```bash
cd website
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# 開発用
python app.py
# 本番用 (例)
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

本番運用では、必ずHTTPS化(Let's Encrypt等)した上で、nginxなどのリバースプロキシ経由で公開してください。
生のIPアドレス+ポート番号(`http://xxx.xxx.xxx.xxx:8080`のような形)で公開するのは、
ユーザーから見て正規のDiscordサイトと区別がつかず、フィッシングと誤認・悪用されるリスクが非常に高いため絶対に避けてください。

### 5. Discordコマンド一覧

| コマンド | 説明 | 権限 |
|---|---|---|
| `/verify-role add` | 付与ロールを追加 | 管理者のみ |
| `/verify-role remove` | 付与ロールを削除 | 管理者のみ |
| `/verify-role list` | 設定済みロール一覧表示 | 管理者のみ |
| `/verify-log-channel` | ログ送信先チャンネル設定 | 管理者のみ |
| `/verify-panel` | 認証パネルを投稿 | 管理者のみ |

## セキュリティ・プライバシーに関する注意

- IPアドレスは個人情報に該当し得ます。サーバーの利用規約・プライバシーポリシーに
  「認証時にIPアドレスを記録し管理者に共有する」旨を明記し、ユーザーに事前周知してください。
- ログ送信先チャンネルは、必ず信頼できる管理者のみが閲覧できるよう権限設定してください。
- `INTERNAL_API_TOKEN` や `FLASK_SECRET_KEY` は十分にランダムな値を使用し、`.env` をGitにコミットしないでください(`.gitignore`で除外済み)。
- 本Botは `identify` スコープのみ要求します。メッセージ閲覧・送信・サーバー参加などの過剰な権限を要求するOAuthアプリは、
  正規のDiscord認証Botであっても疑ってかかるのが安全です。

## ライセンス

MIT License (LICENSEファイル参照)
