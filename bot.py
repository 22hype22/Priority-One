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
import os
TOKEN = os.getenv("DISCORD_TOKEN")

# Where you want the verification embeds to be posted by !setupverify
VERIFY_CHANNEL_ID = 1091587135741624352  # channel id

# Roblox group
ROBLOX_GROUP_ID = 203264927

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


def build_verification_embeds():
    embed_a = discord.Embed(
        title="**Section A**",
        description=(
            "**▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬**\n\n"
            "**A1 |** Be respectful: Treat others with respect, regardless of their race, gender, religion, sexual orientation, or any other personal characteristic. Do not engage in harassment, hate speech, or any form of discrimination.\n\n"
            "**A2 |** No spamming or flooding: Avoid posting excessive or repetitive messages that disrupt the flow of conversation or clog up the chat.\n\n"
            "**A3 |** No NSFW content: Avoid sharing or discussing explicit or inappropriate material. This includes explicit images, videos, or text that are sexually explicit, violent, or offensive.\n\n"
            "**A4 |** No advertising without permission: Avoid promoting or advertising external products, services, or communities without prior permission from the server administrators.\n\n"
            "**A5 |** Respect privacy: Do not share personal information about yourself or others without their consent. This includes real names, addresses, phone numbers, or any other private details.\n\n"
            "**A6 |** No trolling or disruptive behavior: Do not engage in behavior intended to provoke or upset others. This includes intentionally spreading false information, engaging in arguments solely for the purpose of causing conflict, or any other disruptive actions.\n\n"
            "**A7 |** Obey the server staff: Follow the instructions and guidelines provided by the server administrators and moderators. They are responsible for maintaining order and ensuring a positive environment.\n\n"
            "**A8 |** Report violations: If you witness any rule violations or encounter any issues, report them to the server staff or moderators. They will handle the situation accordingly."
        ),
        color=EMBED_COLOR
    )

    embed_b = discord.Embed(
        title="**Section B**",
        description=(
            "**▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬**\n\n"
            "**B1 |** No cheating or hacking: Do not engage in any form of cheating, hacking, or exploiting in online games or platforms. This includes using unauthorized software or techniques to gain an unfair advantage.\n\n"
            "**B2 |** No doxxing: Do not share or request personal information about other users without their consent. This includes their real names, addresses, social media profiles, or any other private details.\n\n"
            "**B3 |** Use appropriate language: Avoid using excessive profanity, vulgar language, or engaging in excessive or unnecessary arguments. Maintain a level of maturity and keep conversations civil.\n\n"
            "**B4 |** No unauthorized bots or automation: Do not use or create bots or automated scripts without permission. This includes spam bots, self-promotion bots, or any other automated tools that may disrupt the server.\n\n"
            "**B5 |** No impersonation: Do not impersonate other users, server staff, or any other individuals or entities. This includes using similar usernames, profile pictures, or attempting to deceive others.\n\n"
            "**B6 |** No posting of illegal or copyrighted content: Do not share or distribute any content that infringes upon copyright laws or violates any applicable local, national, or international laws. This includes pirated software, unauthorized streaming, or any other illegal activities.\n\n"
            "**B7 |** Respect channel organization: Use the appropriate channels or categories for your discussions and avoid posting in the wrong places. This helps to keep conversations organized and easy to follow.\n\n"
            "**B8 |** No excessive self-promotion: Avoid constantly promoting your own content, products, or services. While some communities may allow self-promotion to a certain extent, it's important to be mindful of the server's rules and guidelines regarding promotional content..\n\n"
            "**B9 |** No excessive or unnecessary tagging: Avoid repeatedly tagging or mentioning other users without a valid reason. Excessive tagging can be seen as spammy and disrupts the experience for other users."
        ),
        color=EMBED_COLOR
    )

    embed_c = discord.Embed(
        title="**ADDITIONAL**",
        description=(
            "*Please join our group and invite others!*\n\n"
            "**Group & Discord**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "https://www.roblox.com/communities/203264927\n"
            "https://discord.gg/hWYAE5ESGa"
        ),
        color=EMBED_COLOR
    )

    for e in (embed_a, embed_b, embed_c):
        e.set_author(name="PO | Rules & Regulations")
        e.set_footer(
            text="Remember that these rules are general guidelines, and specific communities may have additional or more specific rules tailored to their needs."
        )

    return [embed_a, embed_b, embed_c]


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

    # Nickname sync
    roblox_name = await roblox_userid_to_username(link_data["roblox_user_id"])
    if not roblox_name:
        return await ctx.reply("❌ Could not fetch your Roblox username.", mention_author=False)

    try:
        await ctx.author.edit(nick=roblox_name, reason="Roblox nickname sync")
    except discord.Forbidden:
        return await ctx.reply(
            "❌ I can’t change your nickname. Give me **Manage Nicknames** and make sure my bot role is above yours.",
            mention_author=False
        )

    await ctx.reply(f"✅ Nickname updated to **{roblox_name}** (Roblox rank: **{role_name}**).", mention_author=False)


# ======================
# ADMIN: SAY (EMBED BUILDER)
# ======================
@bot.command()
@commands.has_permissions(administrator=True)
async def say(ctx, *, message: str):
    """
    Admin-only embed builder.
    Supports multiline + indented continuation lines.
    """
    await ctx.message.delete()

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

        # New field starts only if line begins with key=
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

        # Indented line → append to current field
        elif raw_line.startswith((" ", "\t")) and current_key:
            fields[current_key].append(raw_line.strip())

    title = "\n".join(fields["title"]) if fields["title"] else None
    desc = "\n".join(fields["desc"]) if fields["desc"] else None
    author = "\n".join(fields["author"]) if fields["author"] else None
    footer = "\n".join(fields["footer"]) if fields["footer"] else None
    banner = fields["banner"].strip() if fields["banner"] else None

    # CASE 1: Banner ONLY → send image as normal message
    if banner and not title and not desc:
        await ctx.send(banner)
        return

    # CASE 2: Embed exists
    embed = discord.Embed(
        title=title if title else discord.Embed.Empty,
        description=desc if desc else discord.Embed.Empty,
        color=discord.Color.from_str("#181818")
    )

    if author:
        embed.set_author(name=author)
    if footer:
        embed.set_footer(text=footer)

    await ctx.send(embed=embed)

    # If banner exists, send it OUTSIDE the embed
    if banner:
        await ctx.send(banner)


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
# ADMIN: POST VERIFICATION EMBEDS
# ======================
@bot.command()
@commands.has_permissions(administrator=True)
async def setupverify(ctx):
    """Admin-only: posts verification embeds to VERIFY_CHANNEL_ID."""
    await ctx.message.delete()

    channel = bot.get_channel(VERIFY_CHANNEL_ID)
    if channel is None:
        return await ctx.send("VERIFY_CHANNEL_ID is wrong or I can’t see that channel.")

    embeds = build_verification_embeds()
    await channel.send(embeds=embeds)

    # Send banner as a separate message (outside the embed)
    if BANNER_URL:
        await channel.send(BANNER_URL)

    await ctx.send("✅ Verification message posted.", delete_after=3)



@setupverify.error
async def setupverify_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("You don’t have permission to use that.", mention_author=False)


@bot.command()
@commands.has_permissions(administrator=True)
async def postverify(ctx, channel_id: int = None):
    """
    Admin-only: reposts the verification embeds.
    Usage:
      !postverify
      !postverify <channel_id>
    """
    target_channel = ctx.channel if channel_id is None else bot.get_channel(channel_id)
    if target_channel is None:
        return await ctx.reply("❌ Invalid channel ID or I can’t see that channel.", mention_author=False)

    embeds = build_verification_embeds()
    await target_channel.send(embeds=embeds)
    await ctx.reply("✅ Posted the verification embeds.", mention_author=False)


@postverify.error
async def postverify_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("You don’t have permission to use that.", mention_author=False)
    else:
        await ctx.reply("❌ Usage: `!postverify` or `!postverify <channel_id>`", mention_author=False)


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







