#!/usr/bin/env python3
"""
Discord認証Bot メインファイル
BotとFlaskサーバーを同時実行します
"""

import asyncio
import threading
import sys
from flask_server import app, load_user_data as flask_load_data
from config import FLASK_HOST, FLASK_PORT, BOTTOKEN

def run_flask():
    """Flaskサーバーをスレッドで実行"""
    try:
        print("🌐 Flaskサーバーを起動しています...")
        app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)
    except Exception as e:
        print(f"❌ Flaskサーバーエラー: {e}")

def run_discord_bot():
    """Discord Botを実行"""
    try:
        print("🤖 Discord Botを起動しています...")
        from verify_bot import bot
        bot.run(BOTTOKEN)
    except Exception as e:
        print(f"❌ Discord Botエラー: {e}")

def main():
    """メイン処理"""
    print("=" * 50)
    print("🔐 Discord認証Bot メインプログラム")
    print("=" * 50)
    
    # 設定チェック
    if "token_not_set" in BOTTOKEN.lower() or BOTTOKEN == "Bot トークンをここに入力":
        print("❌ エラー: config.pyのBOTTOKENを設定してください")
        sys.exit(1)
    
    # Flaskサーバーをバックグラウンドで起動
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Discordボットを起動（メインスレッド）
    run_discord_bot()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 プログラムを停止しました")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        sys.exit(1)
