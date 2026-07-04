# Discord認証Bot - verify-bot.xvps.jp

Discord OAuth2を使用した認証ボットです。ユーザーが認証ボタンをクリックするとXserver VPS上の`verify-bot.xvps.jp`にリダイレクトされ、Discordアカウント情報を登録できます。

## 🎯 主な機能

- **Discord OAuth2認証**: セキュアなOAuth2フローで認証
- **ユーザーデータ管理**: 認証ユーザーの情報をJSON形式で保存
- **自動サーバー参加**: アクセストークンを使用してユーザーをサーバーに追加
- **Discordコマンド連携**: Botコマンドで認証ユーザーを管理
- **レスポンシブUI**: モダンなWebインターフェース

## 📦 プロジェクト構成

```
├── config.py              # 📝 設定ファイル（要編集）
├── verify_bot.py          # 🤖 Discord Bot本体
├── flask_server.py        # 🌐 Flaskサーバー
├── main.py               # ▶️ メイン実行ファイル
├── requirements.txt       # 📚 Python依存パッケージ
├── deploy.sh             # 🚀 VPSデプロイスクリプト
├── SETUP_GUIDE.md        # 📖 詳細セットアップガイド
└── README.md             # このファイル
```

## 🚀 クイックスタート

### 1. Discord Developer Portalでの準備（5分）

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. **「New Application」** → アプリケーション名を入力
3. **Bot タブ** → **「Add Bot」** でBotを作成
4. **TOKEN**をコピー
5. **OAuth2 → General** でCLIENT IDとCLIENT SECRETをコピー
6. **Redirects**に以下を追加（末尾の`/`を忘れずに）：
   ```
   https://verify-bot.xvps.jp/callback/
   ```

### 2. ローカルセットアップ（3分）

```bash
# ファイルをダウンロード
git clone <repo_url>
cd verify-bot

# config.pyを編集
# 取得した情報を以下に入力：
# - BOTTOKEN
# - CLIENT_ID  
# - CLIENT_SECRET

# 依存パッケージをインストール
pip install -r requirements.txt

# ローカルテスト起動
python main.py
```

### 3. VPSへのデプロイ（5分）

```bash
# deploy.shのパーミッション変更
chmod +x deploy.sh

# VPS接続情報を設定
export VPS_USER="your-username"
export VPS_HOST="verify-bot.xvps.jp"

# デプロイ実行
./deploy.sh
```

## 📋 ファイル説明

### config.py
Discord Developer Portalから取得した認証情報とサーバー設定を記載します。

**必須設定:**
- `BOTTOKEN`: Botのトークン
- `CLIENT_ID`: OAuth2のクライアントID
- `CLIENT_SECRET`: OAuth2のクライアントシークレット
- `REDIRECT_URI`: コールバックURL（`https://verify-bot.xvps.jp/callback`）

### verify_bot.py
Discord.pyを使用したBot本体です。以下のコマンドを実装：

| コマンド | 説明 |
|---------|------|
| `!button [title \| description]` | 認証ボタンを表示 |
| `!call` | 全登録ユーザーを追加 |
| `!request1 <user_id>` | 指定ユーザーを追加 |
| `!check <user_id>` | ユーザー情報を確認 |
| `!datacheck` | 登録統計を表示 |
| `!delkey <user_id>` | ユーザー情報を削除 |

### flask_server.py
FlaskサーバーがOAuth2コールバックを処理します。

**エンドポイント:**
- `/` - メインページ
- `/auth` - Discord認証へのリダイレクト
- `/callback` - OAuth2コールバック（ユーザーデータ保存）

### main.py
BotとFlaskサーバーを並行実行します。

## 🔐 セキュリティ

### 本番環境での推奨事項

1. **データベース化**
   ```python
   # JSON → SQLite/PostgreSQL への移行を推奨
   # パフォーマンスとセキュリティが向上
   ```

2. **環境変数の使用**
   ```bash
   # .env ファイルで管理
   export BOTTOKEN="..."
   export CLIENT_SECRET="..."
   ```

3. **SSL/TLS設定**
   - Let's Encryptで無料証明書を取得
   - Nginxでリバースプロキシを設定

4. **CORS設定**
   ```python
   # CORS制限を追加
   from flask_cors import CORS
   CORS(app, resources={r"/api/*": {"origins": ["verify-bot.xvps.jp"]}})
   ```

5. **レート制限**
   ```python
   # Flask-Limiter で認証エンドポイントを保護
   from flask_limiter import Limiter
   ```

## 📊 ユーザーデータ形式

認証されたユーザー情報は`user_data.json`に保存されます：

```json
{
  "123456789": {
    "user_id": "123456789",
    "username": "example_user",
    "email": "user@example.com",
    "avatar": "avatar_hash",
    "access_token": "...",
    "refresh_token": "...",
    "token_expires_at": "2024-12-31T12:00:00",
    "registered_at": "2024-12-24T10:00:00"
  }
}
```

**⚠️ 注意:** `access_token`と`refresh_token`は機密情報です。

## 🔄 トークンリフレッシュ

アクセストークンは7日間で有効期限切れになります。リフレッシュトークンを使用して更新できます：

```python
async def refresh_access_token(refresh_token):
    async with aiohttp.ClientSession() as session:
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        async with session.post(
            "https://discord.com/api/v10/oauth2/token",
            data=data
        ) as resp:
            return await resp.json()
```

## 🐛 トラブルシューティング

### ボットが応答しない
```bash
# ボットが起動しているか確認
ps aux | grep main.py

# ログを確認
sudo journalctl -u verify-bot -f
```

### 認証に失敗する
- リダイレクトURIが設定と一致しているか確認
- CLIENT_IDとCLIENT_SECRETが正しいか確認
- Botが対象サーバーに参加しているか確認

### Flaskサーバーが起動しない
```bash
# ポート競合を確認
sudo lsof -i :5000

# ポート変更の場合は config.py で FLASK_PORT を変更
```

## 🔧 カスタマイズ

### カスタムボタンデザイン

`flask_server.py`の`index()`関数のHTMLをカスタマイズできます：

```python
# スタイルを変更
.auth-button {
    background: #your-color;
    border-radius: 5px;  # 角の丸さ
}
```

### ロール自動付与

認証時にロールを自動付与したい場合：

```python
# verify_bot.py に追加
@bot.event
async def on_member_update(before, after):
    if str(after.id) in user_data:
        role = after.guild.get_role(YOUR_ROLE_ID)
        if role:
            await after.add_roles(role)
```

## 📞 サポート・問題報告

問題が発生した場合：

1. **ログを確認**
   ```bash
   sudo journalctl -u verify-bot -n 100
   ```

2. **SETUP_GUIDE.md のトラブルシューティングを参照**

3. **Discordコミュニティに質問**

## 📄 ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 🤝 貢献

改善提案やバグ報告はIssuesでお願いします。

---

**最終更新**: 2024年12月24日  
**バージョン**: 1.0  
**対応Python**: 3.8+  
**対応discord.py**: 2.3+
