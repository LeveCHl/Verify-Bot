import discord
from discord.ext import commands
import asyncio
import json
import os
from datetime import datetime

# 設定をインポート
from config import (
    BOTTOKEN, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI,
    FLASK_HOST, FLASK_PORT, DATA_FILE, SECRET_KEY
)

# Intents設定
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

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

def add_user(user_id, user_info):
    """ユーザー情報を追加"""
    user_data[str(user_id)] = {
        **user_info,
        "registered_at": datetime.now().isoformat(),
        "token_expires_at": user_info.get("token_expires_at", None)
    }
    save_user_data()

def check_user_exists(user_id):
    """ユーザーが登録済みか確認"""
    return str(user_id) in user_data

def delete_user(user_id):
    """ユーザー情報を削除"""
    if str(user_id) in user_data:
        del user_data[str(user_id)]
        save_user_data()
        return True
    return False

def get_user_info(user_id):
    """ユーザー情報を取得"""
    return user_data.get(str(user_id), None)

@bot.event
async def on_ready():
    """ボットが起動した時の処理"""
    load_user_data()
    print(f"✅ Bot is ready! Logged in as {bot.user}")
    print(f"📊 Currently {len(user_data)} users registered")
    # ボットのステータスを設定
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"認証 | verify-bot.xvps.jp"
    ))

@bot.command(name="button", help="認証ボタンを表示")
async def button_command(ctx, *, args=None):
    """
    認証リンクとロール付与のボタンを表示
    使用例: !button タイトル | 説明文
    """
    try:
        if args:
            parts = args.split("|")
            title = parts[0].strip()
            description = parts[1].strip() if len(parts) > 1 else "Discord認証してください"
        else:
            title = "✨ Discord 認証"
            description = "以下のボタンをクリックして、Discord認証を完了してください。"

        # 認証URLを生成
        scopes = "identify guilds.join"
        auth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope={scopes}"

        # Embed作成
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue()
        )
        embed.add_field(
            name="認証リンク",
            value=f"[ここをクリック]({auth_url})",
            inline=False
        )
        embed.set_footer(text="認証にはDiscordアカウントが必要です")

        # ボタン付きViewを作成
        view = AuthView(auth_url)
        
        await ctx.send(embed=embed, view=view)
    except Exception as e:
        await ctx.send(f"❌ エラーが発生しました: {e}")

@bot.command(name="call", help="全登録ユーザーをサーバーに追加")
async def call_command(ctx):
    """
    JSONに保存されたユーザー全員を追加
    注意: 誤爆に気をつけてください
    """
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ 管理者権限が必要です")
        return

    try:
        added_count = 0
        failed_count = 0
        errors = []

        for user_id, user_info in user_data.items():
            try:
                if "access_token" in user_info:
                    # ユーザーをサーバーに追加
                    member = await add_user_to_guild(
                        ctx.guild.id,
                        user_id,
                        user_info["access_token"]
                    )
                    if member:
                        added_count += 1
                    else:
                        failed_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"User {user_id}: {str(e)}")

        embed = discord.Embed(
            title="📊 ユーザー追加結果",
            color=discord.Color.green()
        )
        embed.add_field(name="成功", value=f"{added_count}人", inline=True)
        embed.add_field(name="失敗", value=f"{failed_count}人", inline=True)
        
        if errors:
            embed.add_field(name="エラー詳細", value="\n".join(errors[:5]), inline=False)
        
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ エラーが発生しました: {e}")

@bot.command(name="request1", help="指定ユーザーをサーバーに追加")
async def request1_command(ctx, user_id: str):
    """指定したIDのユーザーを追加"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ 管理者権限が必要です")
        return

    try:
        user_info = get_user_info(user_id)
        if not user_info:
            await ctx.send(f"❌ ユーザーID {user_id} の情報が見つかりません")
            return

        if "access_token" not in user_info:
            await ctx.send(f"❌ ユーザーID {user_id} のアクセストークンがありません")
            return

        member = await add_user_to_guild(
            ctx.guild.id,
            user_id,
            user_info["access_token"]
        )

        if member:
            await ctx.send(f"✅ ユーザー ID: {user_id} をサーバーに追加しました")
        else:
            await ctx.send(f"❌ ユーザー ID: {user_id} の追加に失敗しました")
    except Exception as e:
        await ctx.send(f"❌ エラー: {e}")

@bot.command(name="check", help="ユーザー登録確認")
async def check_command(ctx, user_id: str):
    """指定したユーザーIDの情報が登録されているか確認"""
    user_info = get_user_info(user_id)
    
    if user_info:
        embed = discord.Embed(
            title="✅ ユーザー登録情報",
            color=discord.Color.green()
        )
        embed.add_field(name="ユーザーID", value=user_id, inline=False)
        embed.add_field(name="ユーザー名", value=user_info.get("username", "N/A"), inline=True)
        embed.add_field(name="登録日時", value=user_info.get("registered_at", "N/A"), inline=True)
        
        if user_info.get("token_expires_at"):
            embed.add_field(name="トークン有効期限", value=user_info.get("token_expires_at"), inline=True)
        
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ ユーザーID {user_id} は登録されていません")

@bot.command(name="datacheck", help="登録ユーザー数確認")
async def datacheck_command(ctx):
    """JSONに何人の情報が登録されているか確認"""
    embed = discord.Embed(
        title="📊 登録情報統計",
        color=discord.Color.blue()
    )
    embed.add_field(name="登録ユーザー数", value=f"{len(user_data)}人", inline=False)
    
    # 登録日が最新のユーザー3人
    if user_data:
        recent_users = sorted(
            user_data.items(),
            key=lambda x: x[1].get("registered_at", ""),
            reverse=True
        )[:3]
        
        recent_text = "\n".join([
            f"• {uid}: {info.get('username', 'Unknown')}"
            for uid, info in recent_users
        ])
        embed.add_field(name="最近登録されたユーザー", value=recent_text, inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name="delkey", help="ユーザー登録情報削除")
async def delkey_command(ctx, user_id: str):
    """指定したユーザーIDの登録情報を削除"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ 管理者権限が必要です")
        return

    if delete_user(user_id):
        await ctx.send(f"✅ ユーザーID {user_id} の情報を削除しました")
    else:
        await ctx.send(f"❌ ユーザーID {user_id} の情報は見つかりません")

# ボタン用のView
class AuthView(discord.ui.View):
    def __init__(self, auth_url):
        super().__init__()
        self.auth_url = auth_url
    
    @discord.ui.button(label="🔐 Discord認証", style=discord.ButtonStyle.link, url=None)
    async def auth_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass
    
    def __init__(self, auth_url):
        super().__init__()
        # URLボタンを動的に追加
        button = discord.ui.Button(
            label="🔐 Discord認証",
            style=discord.ButtonStyle.link,
            url=auth_url
        )
        self.add_item(button)

async def add_user_to_guild(guild_id, user_id, access_token):
    """
    ユーザーをギルドに追加
    OAuth2のaccess_tokenを使用
    """
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "access_token": access_token
            }
            
            url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}"
            
            async with session.put(url, json=data, headers=headers) as resp:
                if resp.status == 201 or resp.status == 204:
                    return True
                else:
                    print(f"Failed to add user {user_id}: {resp.status} {await resp.text()}")
                    return False
    except Exception as e:
        print(f"Error adding user to guild: {e}")
        return False

# ボット起動
if __name__ == "__main__":
    try:
        bot.run(BOTTOKEN)
    except Exception as e:
        print(f"❌ ボット起動エラー: {e}")
