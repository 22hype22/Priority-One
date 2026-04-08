import io
import discord
from discord.ext import commands
import aiohttp
import json
import os
import traceback

TOKEN = os.getenv("DISCORD_TOKEN")

ROBLOX_GROUP_ID = 234565642

ROBLOX_TO_DISCORD_ROLE = {
    "community member": [1091583538148679821],
    "vip": [
        1091583538148679821,
        1103177486658977853,
    ],
    "developer": [
        1091583538148679821,
        1463061109174046957,
        1091575484699119677,
    ],
    "senior developer": [
        1091583538148679821,
        1463061197392969821,
        1091575484699119677,
    ],
    "administration": [
        1103516006099468448,
        1128101474073841684,
        1091575484699119677,
    ],
}

LINKS_FILE = "roblox_links.json"
EMBED_COLOR = discord.Color.from_str("#181818")

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

def parse_say_fields(message: str) -> dict:
    """
    Parse key=value fields from a !say message.
    Supported keys: author (a), title (t), desc/description (d), footer (f), banner (b)
    Continuation lines (indented) append to the current key.
    Returns a dict with keys: author, title, desc, footer, banner
    All values are strings or None if not provided.
    """
    fields = {
        "author": [],
        "title": [],
        "desc": [],
        "footer": [],
        "banner": [],
    }
    KEY_ALIASES = {
        "author": "author", "a": "author",
        "title": "title",   "t": "title",
        "desc": "desc",     "description": "desc", "d": "desc",
        "footer": "footer", "f": "footer",
        "banner": "banner", "b": "banner",
    }
    current_key = None

    for raw_line in message.splitlines():
        line = raw_line.rstrip()

        # Blank lines reset continuation
        if not line.strip():
            current_key = None
            continue

        # Continuation line (indented)
        if raw_line.startswith((" ", "\t")) and current_key:
            fields[current_key].append(raw_line.strip())
            continue

        # Key=value line
        if "=" in line:
            key_raw, value = line.split("=", 1)
            key = key_raw.strip().lower()
            value = value.strip()

            if key in KEY_ALIASES:
                current_key = KEY_ALIASES[key]
                if value:
                    fields[current_key] = [value]
                else:
                    fields[current_key] = []
            else:
                current_key = None

    return {k: "\n".join(v) if v else None for k, v in fields.items()}


async def fetch_image_bytes(url: str, session: aiohttp.ClientSession):
    """Fetch raw image bytes from a URL. Returns (bytes, filename) or raises."""
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ValueError(f"HTTP {resp.status} when fetching image")
        data = await resp.read()
        # Try to get a filename from the URL path
        filename = url.split("?")[0].split("/")[-1] or "image.png"
        if "." not in filename:
            filename += ".png"
        return data, filename


async def resolve_banner(ctx, fields: dict, session: aiohttp.ClientSession):
    """
    Returns a discord.File for the banner, or None.
    Priority: attachment on message > banner= URL > None
    """
    # 1) File attachment takes priority
    if ctx.message.attachments:
        att = ctx.message.attachments[0]
        try:
            data, filename = await fetch_image_bytes(att.url, session)
            buf = io.BytesIO(data)
            buf.seek(0)
            return discord.File(fp=buf, filename=filename)
        except Exception as e:
            raise RuntimeError(f"Failed to download attachment: {e}")

    # 2) banner= URL
    if fields.get("banner"):
        url = fields["banner"].strip()
        try:
            data, filename = await fetch_image_bytes(url, session)
            buf = io.BytesIO(data)
            buf.seek(0)
            return discord.File(fp=buf, filename=filename)
        except Exception as e:
            raise RuntimeError(f"Failed to download banner URL: {e}")

    return None


# ======================
# ROBLOX LINK + UPDATE
# ======================

async def roblox_username_to_userid(username: str):
    """Resolve a Roblox username to a user ID via the Roblox API."""
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": False}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            users = data.get("data", [])
            return users[0]["id"] if users else None

async def roblox_group_role_name(user_id: int, group_id: int):
    """Get the role name of a Roblox user in a group."""
    url = f"https://groups.roblox.com/v1/users/{user_id}/groups/roles"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            for entry in data.get("data", []):
                if entry["group"]["id"] == group_id:
                    return entry["role"]["name"]
            return None

@bot.command()
async def link(ctx, roblox_username: str):
    user_id = await roblox_username_to_userid(roblox_username)
    if user_id is None:
        return await ctx.reply("❌ Roblox username not found.", mention_author=False)

    links = load_links()
    links[str(ctx.author.id)] = {
        "roblox_username": roblox_username,
        "roblox_user_id": user_id,
    }
    save_links(links)
    await ctx.reply(f"✅ Linked you to **{roblox_username}**.", mention_author=False)

@bot.command()
async def update(ctx):
    if ctx.guild is None:
        return await ctx.reply("Use this in the server.", mention_author=False)

    links = load_links()
    link_data = links.get(str(ctx.author.id))
    if not link_data:
        return await ctx.reply(
            "You aren't linked yet. Use `!link YourRobloxUsername` first.",
            mention_author=False,
        )

    role_name = await roblox_group_role_name(link_data["roblox_user_id"], ROBLOX_GROUP_ID)
    if role_name is None:
        return await ctx.reply("❌ Join the Roblox group then try again.", mention_author=False)

    role_name_lower = role_name.lower()
    if role_name_lower not in ROBLOX_TO_DISCORD_ROLE:
        return await ctx.reply(f"⚠️ Rank **{role_name}** isn't set up yet.", mention_author=False)

    roles = [
        ctx.guild.get_role(r)
        for r in ROBLOX_TO_DISCORD_ROLE[role_name_lower]
        if ctx.guild.get_role(r)
    ]

    try:
        await ctx.author.add_roles(*roles, reason="Roblox role sync")
    except discord.Forbidden:
        return await ctx.reply("❌ Move the bot role ABOVE all synced roles.", mention_author=False)

    await ctx.reply(f"✅ Roles synced for **{role_name}**.", mention_author=False)


# ======================
# SAY COMMAND
# ======================
# Usage:
#   !say          — plain text output, supports all fields
#   !say embed    — embedded message output
#
# Fields (all optional, any combination):
#   author= or a=
#   title=  or t=
#   desc=   or description= or d=
#   footer= or f=
#   banner= or b=   (paste a URL, or attach a file, or both — attachment wins)
#
# Multiline values: use shift+enter and indent continuation lines.

@bot.command()
@commands.has_permissions(administrator=True)
async def say(ctx):
    # Everything after !say, leading/trailing whitespace stripped
    after_cmd = ctx.message.content[len(ctx.prefix + ctx.invoked_with):].strip()

    # First token determines mode (split handles newlines from shift+enter)
    tokens = after_cmd.split(None, 1)
    first = tokens[0].lower() if tokens else ""

    if first == "embed":
        use_embed = True
        message = tokens[1].strip() if len(tokens) > 1 else ""
    else:
        use_embed = False
        message = after_cmd

    # Save channel before deletion — ctx.send after delete still works but
    # using channel.send is explicit and safe
    channel = ctx.channel

    async with aiohttp.ClientSession() as session:
        # Parse fields
        fields = parse_say_fields(message)

        # Resolve banner BEFORE deleting the message (attachment URL expires after delete)
        try:
            banner_file = await resolve_banner(ctx, fields, session)
        except RuntimeError as e:
            return await ctx.reply(f"❌ {e}", mention_author=False)

        # Delete the command message
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            return await ctx.reply(
                "❌ I need **Manage Messages** to delete your command.",
                mention_author=False,
            )

        # Send output
        try:
            if use_embed:
                embed = discord.Embed(color=EMBED_COLOR)
                if fields["title"]:
                    embed.title = fields["title"]
                if fields["desc"]:
                    embed.description = fields["desc"]
                if fields["author"]:
                    embed.set_author(name=fields["author"])
                if fields["footer"]:
                    embed.set_footer(text=fields["footer"])
                if banner_file:
                    embed.set_image(url=f"attachment://{banner_file.filename}")
                    await channel.send(file=banner_file, embed=embed)
                else:
                    await channel.send(embed=embed)

            else:
                # Plain text — stack fields as formatted lines
                lines = []
                if fields["author"]:
                    lines.append(f"**{fields['author']}**")
                if fields["title"]:
                    lines.append(f"**{fields['title']}**")
                if fields["desc"]:
                    lines.append(fields["desc"])
                if fields["footer"]:
                    lines.append(f"-# {fields['footer']}")

                text = "\n".join(lines) if lines else None
                if text:
                    await channel.send(text)
                if banner_file:
                    await channel.send(file=banner_file)

        except Exception as e:
            traceback.print_exc()
            await channel.send(
                f"❌ Failed to post: `{type(e).__name__}: {str(e)[:180]}`"
            )

@say.error
async def say_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("❌ You don't have permission to use this.", mention_author=False)
# ======================
# STARTUP
# ======================

@bot.event
async def on_ready():
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="Priority One"),
    )
    print(f"Logged in as {bot.user}")


if __name__ == "__main__":
    bot.run(TOKEN)
