# ======================
# DISCORD BOT (FULL FILE)
# Paste this into bot.py
# ======================

import discord
from discord.ext import commands
import aiohttp
import json
import os

# ======================
# CONFIG (EDIT THESE)
# ======================

# IMPORTANT: Do NOT leave your real token in code if you share screenshots.
# If you already posted your token anywhere, reset it in the Discord Developer Portal.
TOKEN = os.getenv("DISCORD_TOKEN")

# Roblox group
ROBLOX_GROUP_ID = 234565642

# Roblox role name -> Discord role IDs (can be more than one role)
ROBLOX_TO_DISCORD_ROLE = {
    "community member": [1091583538148679821],

    "vip": [
        1091583538148679821,  # community member
        1103177486658977853,  # vip
    ],

    "developer": [
        1091583538148679821,  # community member
        1463061109174046957,  # developer
        1091575484699119677,  # developer team
    ],

    "senior developer": [
        1091583538148679821,  # community member
        1463061197392969821,  # senior developer
        1091575484699119677,  # developer team
    ],

    "administration": [
        1103516006099468448,  # +
        1128101474073841684,  # administration
        1091575484699119677,  # developer team
    ],
}

# File where linked Discord->Roblox accounts are stored
LINKS_FILE = "roblox_links.json"

# ======================
# BANNER (PASTE YOUR URL HERE)
# This is where you paste your banner for the end of embeds.
# Must be a DIRECT image link (ends in .png/.jpg/.gif) or Discord CDN link.
# Example:
# BANNER_URL = "https://cdn.discordapp.com/attachments/.../banner.png"
# ======================
BANNER_URL = "https://YOUR-DIRECT-IMAGE-LINK.png"

# Styling
EMBED_COLOR = discord.Color.from_str("#181818")


# ======================
# INTENTS / BOT
# ======================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ======================
# HELPERS
# ======================
def load_links():
    if not os.path.exists(LINKS_FILE):
        return {}
    with open(LINKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_links(data):
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def apply_banner(embed: discord.Embed) -> discord.Embed:
    """Adds banner image to the bottom of the embed if BANNER_URL is set."""
    if BANNER_URL:
        embed.set_image(url=BANNER_URL)
    return embed


async def roblox_username_to_userid(username: str):
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": False}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as r:
            if r.status != 200:
                return None
            data = await r.json()

    items = data.get("data", [])
    if not items:
        return None
    return items[0].get("id")


async def roblox_userid_to_username(user_id: int):
    url = f"https://users.roblox.com/v1/users/{user_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            if r.status != 200:
                return None
            data = await r.json()
    return data.get("name")


async def roblox_group_role_name(user_id: int, group_id: int):
    url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            if r.status != 200:
                return None
            data = await r.json()

    for g in data.get("data", []):
        if g.get("group", {}).get("id") == group_id:
            return g.get("role", {}).get("name")
    return None


# ======================
# ROBLOX LINK + UPDATE
# ======================
@bot.command()
async def link(ctx, roblox_username: str):
    user_id = await roblox_username_to_userid(roblox_username)
    if user_id is None:
        return await ctx.reply("❌ Roblox username not found.", mention_author=False)

    links = load_links()
    links[str(ctx.author.id)] = {"roblox_username": roblox_username, "roblox_user_id": user_id}
    save_links(links)

    await ctx.reply(f"✅ Linked you to **{roblox_username}**.", mention_author=False)


@bot.command()
async def update(ctx):
    if ctx.guild is None:
        return await ctx.reply("Use this in the server.", mention_author=False)

    links = load_links()
    link_data = links.get(str(ctx.author.id))
    if not link_data:
        return await ctx.reply("You aren’t linked yet. Use `!link YourRobloxUsername` first.", mention_author=False)

    role_name = await roblox_group_role_name(link_data["roblox_user_id"], ROBLOX_GROUP_ID)
    if role_name is None:
        return await ctx.reply("❌ I can’t find you in the Roblox group. Join the group, then try again.", mention_author=False)

    role_name_lower = role_name.lower()

    # ===== GIVE ROLES =====
    if role_name_lower not in ROBLOX_TO_DISCORD_ROLE:
        return await ctx.reply(f"⚠️ Rank **{role_name}** has no role setup yet.", mention_author=False)

    role_ids = ROBLOX_TO_DISCORD_ROLE[role_name_lower]

    roles_to_add = []
    for rid in role_ids:
        role = ctx.guild.get_role(rid)
        if role:
            roles_to_add.append(role)

    try:
        await ctx.author.add_roles(*roles_to_add, reason="Roblox role sync")
    except discord.Forbidden:
        return await ctx.reply("❌ Bot can't give roles. Move bot role ABOVE other roles.", mention_author=False)

    # ===== NICKNAME =====
    roblox_name = await roblox_userid_to_username(link_data["roblox_user_id"])
    if roblox_name:
        try:
            await ctx.author.edit(nick=roblox_name)
        except:
            pass

    await ctx.reply(f"✅ Roles synced for **{role_name}**.", mention_author=False)



# ======================
# ADMIN: SAY (EMBED BUILDER)
# ======================
@bot.command()
@commands.has_permissions(administrator=True)
async def say(ctx, *, message: str):
    """
    Admin-only embed builder.
    Supports multiline + indented continuation lines.
    If you attach an image, it will automatically be used as banner.
    """

    fields = {
        "author": [],
        "title": [],
        "desc": [],
        "footer": [],
        "banner": None,
    }

    current_key = None
    lines = message.splitlines()

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip():
            continue

        if "=" in line and not line.startswith((" ", "\t")):
            key, value = line.split("=", 1)
            key = key.strip().lower()
            value = value.rstrip()

            if key in ("author", "a"):
                current_key = "author"
                fields[current_key] = [value]
            elif key in ("title", "t"):
                current_key = "title"
                fields[current_key] = [value]
            elif key in ("desc", "description", "d"):
                current_key = "desc"
                fields[current_key] = [value]
            elif key in ("footer", "f"):
                current_key = "footer"
                fields[current_key] = [value]
            elif key in ("banner", "image", "img", "b"):
                fields["banner"] = value.strip()
                current_key = None
            else:
                current_key = None

        elif raw_line.startswith((" ", "\t")) and current_key:
            fields[current_key].append(raw_line.strip())

    title = "\n".join(fields["title"]) if fields["title"] else None
    desc = "\n".join(fields["desc"]) if fields["desc"] else None
    author = "\n".join(fields["author"]) if fields["author"] else None
    footer = "\n".join(fields["footer"]) if fields["footer"] else None
    banner = fields["banner"]

    embed = None
    if title or desc or author or footer:
        embed = discord.Embed(
            title=title if title else discord.Embed.Empty,
            description=desc if desc else discord.Embed.Empty,
            color=discord.Color.from_str("#181818"),
        )
        if author:
            embed.set_author(name=author)
        if footer:
            embed.set_footer(text=footer)

    attachment = ctx.message.attachments[0] if ctx.message.attachments else None

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    # If banner link used
    if banner:
        await ctx.send(banner)
        return

    # If image attached, put it INSIDE the embed
    if attachment and embed:
        try:
            file = await attachment.to_file()
            embed.set_image(url=f"attachment://{file.filename}")
            await ctx.send(embed=embed, file=file)
        except discord.Forbidden:
            await ctx.send("❌ I need **Attach Files** permission to send the banner image.")
        except Exception as e:
            await ctx.send("❌ Banner failed. Check Railway logs.")


@say.error
async def say_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("You don’t have permission to use that.", mention_author=False)

# ======================
# ADMIN: ANNOUNCE (EMBED)
# ======================
@bot.command()
@commands.has_permissions(administrator=True)
async def announce(ctx, *, text: str):
    """
    Admin-only embed announcement.
    Usage:
      !announce Title | message here
    """
    await ctx.message.delete()

    if "|" in text:
        title, desc = [s.strip() for s in text.split("|", 1)]
    else:
        title, desc = "Announcement", text.strip()

    embed = discord.Embed(title=title, description=desc, color=EMBED_COLOR)
    embed.set_footer(text=f"Posted by {ctx.author.display_name}")
    apply_banner(embed)

    await ctx.send(embed=embed)


@announce.error
async def announce_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("You don’t have permission to use that.", mention_author=False)

# ======================
# STARTUP
# ======================
@bot.event
async def on_ready():
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="Roblox Verification")
    )
    print(f"Logged in as {bot.user}")


if __name__ == "__main__":
    bot.run(TOKEN)
