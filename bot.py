# ======================
# DISCORD BOT (FULL FILE)
# ======================

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
        return await ctx.reply("❌ Join the Roblox group then try again.", mention_author=False)

    role_name_lower = role_name.lower()

    if role_name_lower not in ROBLOX_TO_DISCORD_ROLE:
        return await ctx.reply(f"⚠️ Rank **{role_name}** not setup yet.", mention_author=False)

    roles = [ctx.guild.get_role(r) for r in ROBLOX_TO_DISCORD_ROLE[role_name_lower] if ctx.guild.get_role(r)]

    try:
        await ctx.author.add_roles(*roles, reason="Roblox role sync")
    except discord.Forbidden:
        return await ctx.reply("❌ Move bot role ABOVE all roles.", mention_author=False)

    await ctx.reply(f"✅ Roles synced for **{role_name}**.", mention_author=False)

# ======================
# SAY COMMAND (FINAL)
# ======================
@bot.command()
@commands.has_permissions(administrator=True)
async def say(ctx, *, message: str):
    fields = {"author": [], "title": [], "desc": [], "footer": []}
    current_key = None

    # grab attachment BEFORE deleting message
    attachment = ctx.message.attachments[0] if ctx.message.attachments else None

    for raw_line in message.splitlines():
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
            else:
                current_key = None

        elif raw_line.startswith((" ", "\t")) and current_key:
            fields[current_key].append(raw_line.strip())

    title = "\n".join(fields["title"]) if fields["title"] else None
    desc = "\n".join(fields["desc"]) if fields["desc"] else None
    author = "\n".join(fields["author"]) if fields["author"] else None
    footer = "\n".join(fields["footer"]) if fields["footer"] else None

    embed = discord.Embed(
        title=title if title else discord.Embed.Empty,
        description=desc if desc else discord.Embed.Empty,
        color=EMBED_COLOR,
    )
    if author:
        embed.set_author(name=author)
    if footer:
        embed.set_footer(text=footer)

    try:
        # delete your message FIRST
        await ctx.message.delete()

        # send embed
        await ctx.send(embed=embed)

        # send banner FULL WIDTH outside embed
        if attachment:
            file = await attachment.to_file()
            await ctx.send(file=file)

    except Exception as e:
        traceback.print_exc()
        await ctx.send(f"❌ Error: {e}")

@say.error
async def say_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("You don’t have permission.", mention_author=False)

# ======================
# STARTUP
# ======================
@bot.event
async def on_ready():
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="Priority One")
    )
    print(f"Logged in as {bot.user}")

if __name__ == "__main__":
    bot.run(TOKEN)
