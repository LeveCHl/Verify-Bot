# Discord認証Bot 設定ファイル
# Discord Developer Portalから取得した情報を入力してください

BOTTOKEN = "Bot トークンをここに入力"
CLIENT_ID = "OAuth2 CLIENT IDをここに入力"
CLIENT_SECRET = "OAuth2 CLIENT SECRETをここに入力"

# Xserver VPSで構築したサブドメイン
REDIRECT_URI = "https://verify-bot.xvps.jp/callback"

# Flaskサーバーのホスト設定
FLASK_HOST = "0.0.0.0"  # すべてのインターフェースで受け付ける
FLASK_PORT = 5000

# ユーザー情報の保存ファイル
DATA_FILE = "user_data.json"

# ロール付与に使用するロールID (必要に応じて設定)
# ROLE_ID = 123456789  # 自動付与したいロールIDをここに

# セキュリティ設定
SECRET_KEY = "flask_session_secret_key_change_this"  # Flaskセッション用（本番環境では変更必須）
