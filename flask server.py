from flask import Flask, request, redirect, render_template_string
import aiohttp
import asyncio
import json
import os
from datetime import datetime, timedelta
from config import (
    CLIENT_ID, CLIENT_SECRET, REDIRECT_URI,
    FLASK_HOST, FLASK_PORT, DATA_FILE, SECRET_KEY
)

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ユーザーデータを管理する辞書
user_data = {}

def load_user_data():
    """JSONファイルからユーザーデータを読み込む"""
    global user_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
        except:
            user_data = {}
    else:
        user_data = {}

def save_user_data():
    """ユーザーデータをJSONファイルに保存"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

@app.route("/")
def index():
    """メインページ"""
    html = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Discord認証 - verify-bot</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
            }
            
            .container {
                background: white;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
                padding: 40px;
                max-width: 500px;
                text-align: center;
            }
            
            h1 {
                color: #2c3e50;
                margin-bottom: 10px;
                font-size: 28px;
            }
            
            .subtitle {
                color: #7f8c8d;
                margin-bottom: 30px;
                font-size: 14px;
            }
            
            .auth-button {
                display: inline-block;
                background: #5865f2;
                color: white;
                padding: 12px 30px;
                border-radius: 25px;
                text-decoration: none;
                font-weight: bold;
                transition: all 0.3s ease;
                border: none;
                cursor: pointer;
                font-size: 16px;
            }
            
            .auth-button:hover {
                background: #4752c4;
                transform: scale(1.05);
            }
            
            .info {
                background: #ecf0f1;
                border-left: 4px solid #5865f2;
                padding: 15px;
                border-radius: 5px;
                margin-top: 30px;
                text-align: left;
                font-size: 13px;
                color: #34495e;
            }
            
            .info strong {
                display: block;
                margin-bottom: 8px;
                color: #2c3e50;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔐 Discord認証</h1>
            <p class="subtitle">Discordアカウントで認証してください</p>
            
            <a href="/auth" class="auth-button">Discord で認証</a>
            
            <div class="info">
                <strong>ℹ️ このページについて</strong>
                このページを通じてDiscordアカウントを認証すると、あなたの基本情報（ユーザーID、ユーザー名など）がサーバーに保存されます。
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/auth")
def auth():
    """Discord OAuth2認証へリダイレクト"""
    scopes = "identify guilds.join"
    redirect_uri = REDIRECT_URI
    
    auth_url = (
        f"https://discord.com/api/oauth2/authorize?"
        f"client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&scope={scopes}"
        f"&redirect_uri={redirect_uri}"
    )
    
    return redirect(auth_url)

@app.route("/callback")
async def callback():
    """OAuth2コールバック処理"""
    try:
        code = request.args.get("code")
        
        if not code:
            return error_page("認証コードが見つかりません")
        
        # アクセストークンを取得
        token_data = await get_access_token(code)
        
        if not token_data or "access_token" not in token_data:
            return error_page("アクセストークンの取得に失敗しました")
        
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 604800)  # デフォルト7日
        
        # ユーザー情報を取得
        user_info = await get_user_info(access_token)
        
        if not user_info or "id" not in user_info:
            return error_page("ユーザー情報の取得に失敗しました")
        
        # ユーザーデータを保存
        user_id = user_info["id"]
        load_user_data()
        
        token_expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
        
        user_data[str(user_id)] = {
            "user_id": user_id,
            "username": user_info.get("username", "Unknown"),
            "discriminator": user_info.get("discriminator", ""),
            "email": user_info.get("email", ""),
            "avatar": user_info.get("avatar", ""),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": token_expires_at,
            "registered_at": datetime.now().isoformat()
        }
        
        save_user_data()
        
        # 成功ページを表示
        return success_page(user_info)
        
    except Exception as e:
        print(f"Callback Error: {e}")
        return error_page(f"エラーが発生しました: {str(e)}")

async def get_access_token(code):
    """認可コードからアクセストークンを取得"""
    try:
        async with aiohttp.ClientSession() as session:
            data = {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
                "scope": "identify guilds.join"
            }
            
            async with session.post(
                "https://discord.com/api/v10/oauth2/token",
                data=data
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    print(f"Token Error: {resp.status}")
                    return None
    except Exception as e:
        print(f"Get Token Error: {e}")
        return None

async def get_user_info(access_token):
    """アクセストークンからユーザー情報を取得"""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            async with session.get(
                "https://discord.com/api/v10/users/@me",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return None
    except Exception as e:
        print(f"Get User Info Error: {e}")
        return None

def success_page(user_info):
    """成功ページ"""
    username = user_info.get("username", "Unknown")
    user_id = user_info.get("id", "")
    
    html = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>認証成功 - verify-bot</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
            }}
            
            .container {{
                background: white;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
                padding: 40px;
                max-width: 500px;
                text-align: center;
            }}
            
            .success-icon {{
                font-size: 60px;
                margin-bottom: 20px;
            }}
            
            h1 {{
                color: #27ae60;
                margin-bottom: 10px;
                font-size: 28px;
            }}
            
            .user-info {{
                background: #ecf0f1;
                padding: 20px;
                border-radius: 5px;
                margin: 20px 0;
                text-align: left;
            }}
            
            .user-info p {{
                color: #34495e;
                margin: 8px 0;
                font-size: 14px;
            }}
            
            .user-info strong {{
                color: #2c3e50;
            }}
            
            .message {{
                color: #7f8c8d;
                font-size: 14px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✅</div>
            <h1>認証成功</h1>
            
            <div class="user-info">
                <p><strong>ユーザー名:</strong> {username}</p>
                <p><strong>ユーザーID:</strong> {user_id}</p>
            </div>
            
            <p class="message">
                認証が完了しました！<br>
                このタブは閉じてDiscordに戻ってください。
            </p>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

def error_page(message):
    """エラーページ"""
    html = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>エラー - verify-bot</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
            }}
            
            .container {{
                background: white;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
                padding: 40px;
                max-width: 500px;
                text-align: center;
            }}
            
            .error-icon {{
                font-size: 60px;
                margin-bottom: 20px;
            }}
            
            h1 {{
                color: #e74c3c;
                margin-bottom: 10px;
                font-size: 28px;
            }}
            
            .error-message {{
                background: #fadbd8;
                border-left: 4px solid #e74c3c;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
                text-align: left;
                color: #c0392b;
                font-size: 14px;
            }}
            
            .back-button {{
                display: inline-block;
                background: #5865f2;
                color: white;
                padding: 10px 20px;
                border-radius: 25px;
                text-decoration: none;
                transition: all 0.3s ease;
                margin-top: 20px;
            }}
            
            .back-button:hover {{
                background: #4752c4;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="error-icon">❌</div>
            <h1>エラー</h1>
            
            <div class="error-message">
                {message}
            </div>
            
            <a href="/" class="back-button">← 戻る</a>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.errorhandler(404)
def not_found(error):
    return error_page("ページが見つかりません"), 404

@app.errorhandler(500)
def internal_error(error):
    return error_page("サーバーエラーが発生しました"), 500

if __name__ == "__main__":
    # サーバーを起動
    print(f"🚀 Flaskサーバーが起動しました")
    print(f"📡 URL: http://localhost:{FLASK_PORT}")
    print(f"🔗 リダイレクトURI: {REDIRECT_URI}")
    
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
