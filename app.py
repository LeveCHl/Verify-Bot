"""
Ribl Verify - 認証サイト
========================
Discord公式OAuth2を使った認証フロー。
1. ユーザーが /login?guild_id=... にアクセス
2. Discord公式の認証画面 (discord.com/oauth2/authorize) へリダイレクト
3. ユーザーが許可すると /callback に戻ってくる
4. ここでアクセストークンを取得し、ユーザー情報を取得
5. リクエスト元IPアドレスを取得
6. Bot側の内部APIを呼び、ロール付与 + 管理者チャンネルへのログ送信を行う

⚠️ 必ず信頼できる自分のドメイン(HTTPS)で運用してください。
⚠️ IPアドレスを記録する旨は、利用規約・プライバシーポリシーに明記してください。
"""

import os
import secrets
import requests
from flask import Flask, request, redirect, session, render_template, abort
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]

DISCORD_CLIENT_ID = os.environ["DISCORD_CLIENT_ID"]
DISCORD_CLIENT_SECRET = os.environ["DISCORD_CLIENT_SECRET"]
REDIRECT_URI = os.environ["DISCORD_REDIRECT_URI"]  # 例: https://your-domain.example.com/callback
INTERNAL_API_TOKEN = os.environ["INTERNAL_API_TOKEN"]
INTERNAL_API_URL = os.environ.get("INTERNAL_API_URL", "http://127.0.0.1:8090/grant")

DISCORD_API = "https://discord.com/api/v10"
OAUTH_SCOPES = "identify"  # メッセージ閲覧・送信などの権限は要求しない


def get_client_ip() -> str:
    """
    リバースプロキシ(nginx等)配下で運用する前提でX-Forwarded-Forを優先。
    直接公開する場合は remote_addr を使用。
    本番ではプロキシの信頼設定をきちんと行うこと(IP偽装防止)。
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


@app.route("/login")
def login():
    guild_id = request.args.get("guild_id")
    if not guild_id:
        abort(400, "guild_id is required")

    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    session["guild_id"] = guild_id

    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": OAUTH_SCOPES,
        "state": state,
        "prompt": "consent",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return redirect(f"https://discord.com/oauth2/authorize?{query}")


@app.route("/callback")
def callback():
    error = request.args.get("error")
    if error:
        return render_template("result.html", success=False, message="認証がキャンセルされました。")

    code = request.args.get("code")
    state = request.args.get("state")
    if not code or state != session.get("oauth_state"):
        return render_template("result.html", success=False, message="不正なリクエストです。もう一度お試しください。")

    guild_id = session.get("guild_id")
    if not guild_id:
        return render_template("result.html", success=False, message="サーバー情報が見つかりませんでした。")

    # アクセストークン取得
    token_res = requests.post(
        f"{DISCORD_API}/oauth2/token",
        data={
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    if token_res.status_code != 200:
        return render_template("result.html", success=False, message="認証に失敗しました。")

    access_token = token_res.json()["access_token"]

    # ユーザー情報取得
    user_res = requests.get(
        f"{DISCORD_API}/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if user_res.status_code != 200:
        return render_template("result.html", success=False, message="ユーザー情報の取得に失敗しました。")

    user = user_res.json()
    ip_address = get_client_ip()

    # Bot内部APIを呼び、ロール付与+ログ送信
    grant_res = requests.post(
        INTERNAL_API_URL,
        json={
            "guild_id": guild_id,
            "user_id": user["id"],
            "username": f'{user["username"]}',
            "ip_address": ip_address,
        },
        headers={"X-Internal-Token": INTERNAL_API_TOKEN},
        timeout=10,
    )

    if grant_res.status_code == 200:
        result = grant_res.json()
        if result.get("granted_roles"):
            if result.get("already_verified"):
                return render_template(
                    "result.html", success=True,
                    message="あなたは既に認証済みです。ロールも正しく付与されています。",
                )
            return render_template("result.html", success=True, message="認証が完了しました。Discordに戻ってください。")
    return render_template(
        "result.html",
        success=False,
        message="ロールの付与に失敗しました。サーバー管理者にお問い合わせください。",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
