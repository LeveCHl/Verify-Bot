"""
Ribl Verify Bot
================
- /verify-role add   : 認証完了時に付与するロールを追加(管理者のみ)
- /verify-role remove: 付与ロールを削除(管理者のみ)
- /verify-role list  : 現在の設定済みロール一覧を表示
- /verify-log-channel: 認証ログ(IPアドレス等)を送信するチャンネルを設定(管理者のみ)
- /verify-panel      : 認証ボタン付きパネルをそのチャンネルに投稿

認証自体は Web サイト(OAuth2)側で行い、完了後 website/app.py が
このBotの内部APIを叩いてロール付与とログ送信を行う想定。
"""

import os
import sys
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import web
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from shared import db  # noqa: E402

load_dotenv()

DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
INTERNAL_API_TOKEN = os.environ["INTERNAL_API_TOKEN"]  # website -> bot 間の認証用シークレット
VERIFY_URL_BASE = os.environ.get("VERIFY_URL_BASE", "https://your-domain.example.com")
INTERNAL_API_PORT = int(os.environ.get("INTERNAL_API_PORT", "8090"))

intents = discord.Intents.default()
intents.members = True  # ロール付与に必要

bot = commands.Bot(command_prefix="!", intents=intents)


def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)


verify_role_group = app_commands.Group(
    name="verify-role", description="認証時に付与するロールを管理します(管理者のみ)"
)


@verify_role_group.command(name="add", description="認証完了時に付与するロールを追加します")
@app_commands.describe(role="付与するロール")
@is_admin()
async def verify_role_add(interaction: discord.Interaction, role: discord.Role):
    db.add_role(interaction.guild_id, role.id)
    await interaction.response.send_message(
        f"✅ 認証完了時に付与するロールとして **{role.name}** を追加しました。",
        ephemeral=True,
    )


@verify_role_group.command(name="remove", description="付与ロールから削除します")
@app_commands.describe(role="削除するロール")
@is_admin()
async def verify_role_remove(interaction: discord.Interaction, role: discord.Role):
    db.remove_role(interaction.guild_id, role.id)
    await interaction.response.send_message(
        f"🗑️ **{role.name}** を付与ロールから削除しました。", ephemeral=True
    )


@verify_role_group.command(name="list", description="現在設定されている付与ロール一覧を表示します")
@is_admin()
async def verify_role_list(interaction: discord.Interaction):
    role_ids = db.get_roles(interaction.guild_id)
    if not role_ids:
        await interaction.response.send_message("現在、設定されているロールはありません。", ephemeral=True)
        return
    mentions = []
    for rid in role_ids:
        role = interaction.guild.get_role(int(rid))
        mentions.append(role.mention if role else f"(不明なロール: {rid})")
    await interaction.response.send_message(
        "現在の付与ロール:\n" + "\n".join(f"・{m}" for m in mentions), ephemeral=True
    )


bot.tree.add_command(verify_role_group)


@bot.tree.command(name="verify-log-channel", description="認証ログ(IPアドレス等)を送信するチャンネルを設定します(管理者のみ)")
@app_commands.describe(channel="ログを送信するチャンネル(管理者専用チャンネルを推奨)")
@is_admin()
async def verify_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    db.set_log_channel(interaction.guild_id, channel.id)
    await interaction.response.send_message(
        f"✅ 認証ログの送信先を {channel.mention} に設定しました。\n"
        f"⚠️ このチャンネルにはIPアドレスを含む個人情報が送信されます。"
        f"必ず管理者のみが閲覧できるチャンネルに設定してください。",
        ephemeral=True,
    )


class VerifyView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        url = f"{VERIFY_URL_BASE}/login?guild_id={guild_id}"
        self.add_item(discord.ui.Button(label="認証する", style=discord.ButtonStyle.link, url=url))


@bot.tree.command(name="verify-panel", description="認証ボタン付きパネルをこのチャンネルに投稿します(管理者のみ)")
@is_admin()
async def verify_panel(interaction: discord.Interaction):
    role_ids = db.get_roles(interaction.guild_id)
    if not role_ids:
        await interaction.response.send_message(
            "⚠️ まだ付与ロールが設定されていません。先に /verify-role add で設定してください。",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title="認証",
        description="下のボタンから認証を行ってください。\n認証完了後、自動的にロールが付与されます。",
        color=discord.Color.blurple(),
    )
    await interaction.channel.send(embed=embed, view=VerifyView(interaction.guild_id))
    await interaction.response.send_message("✅ 認証パネルを投稿しました。", ephemeral=True)


@verify_role_add.error
@verify_role_remove.error
@verify_role_list.error
@verify_log_channel.error
@verify_panel.error
async def on_admin_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("❌ このコマンドは管理者のみ実行できます。", ephemeral=True)
    else:
        raise error


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")


# ---------------------------------------------------------------
# 内部API: website/app.py からのみ呼び出される(IP送信元はlocalhost想定)
# OAuth認証完了後にロール付与とログ送信を行う
# ---------------------------------------------------------------

async def handle_grant(request: web.Request):
    if request.headers.get("X-Internal-Token") != INTERNAL_API_TOKEN:
        return web.json_response({"error": "unauthorized"}, status=401)

    data = await request.json()
    guild_id = int(data["guild_id"])
    user_id = int(data["user_id"])
    username = data["username"]
    ip_address = data["ip_address"]

    guild = bot.get_guild(guild_id)
    if guild is None:
        return web.json_response({"error": "guild not found"}, status=404)

    member = guild.get_member(user_id) or await guild.fetch_member(user_id)

    already_verified = db.is_verified(guild_id, user_id)
    other_users_same_ip = db.get_distinct_users_for_ip(guild_id, ip_address, exclude_user_id=str(user_id))

    role_ids = db.get_roles(guild_id)
    granted = []

    if already_verified:
        # 既に認証済み: ロールを再付与する必要はないが、現在持っているか念のため確認
        for rid in role_ids:
            role = guild.get_role(int(rid))
            if role and role in member.roles:
                granted.append(role.name)
            elif role:
                try:
                    await member.add_roles(role, reason="認証済みユーザーの再認証(ロール再付与)")
                    granted.append(role.name)
                except discord.Forbidden:
                    pass
    else:
        for rid in role_ids:
            role = guild.get_role(int(rid))
            if role:
                try:
                    await member.add_roles(role, reason="認証完了による自動付与")
                    granted.append(role.name)
                except discord.Forbidden:
                    pass
        if granted:
            db.mark_verified(guild_id, user_id, ip_address)

    db.add_verify_log(guild_id, user_id, username, ip_address, success=bool(granted))

    log_channel_id = db.get_log_channel(guild_id)
    if log_channel_id:
        channel = guild.get_channel(int(log_channel_id))
        if channel:
            embed = discord.Embed(
                title="🔐 認証ログ" + ("(再認証)" if already_verified else ""),
                color=discord.Color.green() if granted else discord.Color.red(),
            )
            embed.add_field(name="ユーザー", value=f"{username} ({member.mention})", inline=False)
            embed.add_field(name="ユーザーID", value=str(user_id), inline=True)
            embed.add_field(name="IPアドレス", value=ip_address, inline=True)
            embed.add_field(
                name="結果",
                value=("付与ロール: " + ", ".join(granted)) if granted else "ロール付与に失敗しました",
                inline=False,
            )
            if other_users_same_ip:
                mentions = []
                for uid in other_users_same_ip:
                    m = guild.get_member(int(uid))
                    mentions.append(m.mention if m else f"(不明なユーザー: {uid})")
                embed.add_field(
                    name="⚠️ 同一IPからの他アカウント",
                    value=(
                        f"このIPアドレスからは過去に {len(other_users_same_ip)} 件の"
                        f"別アカウントの認証履歴があります:\n" + "\n".join(mentions)
                    ),
                    inline=False,
                )
                embed.color = discord.Color.orange()
            await channel.send(embed=embed)

    return web.json_response({
        "granted_roles": granted,
        "already_verified": already_verified,
        "alt_account_warning": bool(other_users_same_ip),
    })


async def start_internal_api():
    app = web.Application()
    app.router.add_post("/grant", handle_grant)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", INTERNAL_API_PORT)
    await site.start()
    print(f"✅ Internal API listening on 127.0.0.1:{INTERNAL_API_PORT}")


async def main():
    db.init_db()
    async with bot:
        bot.loop.create_task(start_internal_api())
        await bot.start(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
