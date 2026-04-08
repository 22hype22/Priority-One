import io
import re
import discord
from discord.ext import commands
from discord import app_commands
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

# Role that can manage tickets (Community Management)
TICKET_STAFF_ROLE_ID = 1126332043517767690

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
tree = bot.tree


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

        if not line.strip():
            current_key = None
            continue

        if raw_line.startswith((" ", "\t")) and current_key:
            fields[current_key].append(raw_line.strip())
            continue

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
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ValueError(f"HTTP {resp.status} when fetching image")
        data = await resp.read()
        filename = url.split("?")[0].split("/")[-1] or "image.png"
        if "." not in filename:
            filename += ".png"
        return data, filename


async def resolve_banner(ctx, fields: dict, session: aiohttp.ClientSession):
    if ctx.message.attachments:
        att = ctx.message.attachments[0]
        try:
            data, filename = await fetch_image_bytes(att.url, session)
            buf = io.BytesIO(data)
            buf.seek(0)
            return discord.File(fp=buf, filename=filename)
        except Exception as e:
            raise RuntimeError(f"Failed to download attachment: {e}")

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
# !say          — plain text
# !say embed    — embedded message
#
# Fields: author=, title=, desc=/description=, footer=, banner=
# Attach a file or paste a URL for banner. Attachment wins over URL.

@bot.command()
@commands.has_permissions(administrator=True)
async def say(ctx):
    after_cmd = ctx.message.content[len(ctx.prefix + ctx.invoked_with):].strip()

    tokens = after_cmd.split(None, 1)
    first = tokens[0].lower() if tokens else ""

    if first == "embed":
        use_embed = True
        message = tokens[1].strip() if len(tokens) > 1 else ""
    else:
        use_embed = False
        message = after_cmd

    channel = ctx.channel

    async with aiohttp.ClientSession() as session:
        fields = parse_say_fields(message)

        try:
            banner_file = await resolve_banner(ctx, fields, session)
        except RuntimeError as e:
            return await ctx.reply(f"❌ {e}", mention_author=False)

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            return await ctx.reply(
                "❌ I need **Manage Messages** to delete your command.",
                mention_author=False,
            )

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
                    if not any([fields["title"], fields["desc"], fields["author"], fields["footer"]]):
                        embed.description = "\u200b"
                    await channel.send(file=banner_file, embed=embed)
                else:
                    await channel.send(embed=embed)

            else:
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
# TICKET SYSTEM
# ======================
# /ticket — slash command, admin only
# Fields: title, description, banner (URL, optional), drop1–drop5
# Users pick a category from the dropdown → private ticket channel created
# Inside ticket: Claim button (staff only) + Close button (staff only)
# Claim: locks channel to claimer + opener only (staff role loses send perms)
# Close: locks channel for everyone

class TicketDropdown(discord.ui.Select):
    def __init__(self, options: list, custom_messages: dict):
        # options is a list of label strings
        # custom_messages is {label: custom_text} for per-category messages
        self.custom_messages = custom_messages
        select_options = [
            discord.SelectOption(label=opt, value=opt)
            for opt in options
        ]
        super().__init__(
            placeholder="Select a category to open a ticket...",
            min_values=1,
            max_values=1,
            options=select_options,
            custom_id="ticket_dropdown",
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        guild = interaction.guild
        user = interaction.user
        staff_role = guild.get_role(TICKET_STAFF_ROLE_ID)

        # Check for existing open ticket
        safe_name = re.sub(r"[^a-z0-9-]", "", user.name.lower().replace(" ", "-"))
        channel_name = f"ticket-{safe_name}"
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            return await interaction.response.send_message(
                f"❌ You already have an open ticket: {existing.mention}",
                ephemeral=True,
            )

        # Find or create Tickets category
        tickets_category = discord.utils.get(guild.categories, name="Tickets")
        if not tickets_category:
            try:
                tickets_category = await guild.create_category(
                    name="Tickets",
                    reason="Auto-created for ticket system",
                )
            except discord.Forbidden:
                tickets_category = None

        # Permission overwrites for new ticket channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
            ),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
            )

        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=tickets_category,
                overwrites=overwrites,
                reason=f"Ticket opened by {user} — {category}",
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to create channels.",
                ephemeral=True,
            )

        # Build intro embed
        custom_msg = self.custom_messages.get(category, "")
        desc = f"Thanks for opening a ticket, {user.mention}!\n**Category:** {category}"
        if custom_msg:
            desc += f"\n\n{custom_msg}"

        embed = discord.Embed(
            title=f"Ticket — {category}",
            description=desc,
            color=EMBED_COLOR,
        )
        embed.set_footer(text=f"Opened by {user.display_name}")

        view = TicketActionView(opener_id=user.id)
        await ticket_channel.send(
            content=user.mention,
            embed=embed,
            view=view,
        )

        await interaction.response.send_message(
            f"✅ Your ticket has been created: {ticket_channel.mention}",
            ephemeral=True,
        )


class TicketActionView(discord.ui.View):
    def __init__(self, opener_id: int = 0):
        super().__init__(timeout=None)
        self.opener_id = opener_id

    def _is_staff(self, member: discord.Member) -> bool:
        return any(r.id == TICKET_STAFF_ROLE_ID for r in member.roles)

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.success,
        emoji="🙋",
        custom_id="ticket_claim",
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can claim tickets.", ephemeral=True
            )

        channel = interaction.channel
        guild = interaction.guild
        staff_role = guild.get_role(TICKET_STAFF_ROLE_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
            ),
            # Claimer gets full access
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
        }

        # Staff role can view but not send — claimer handles it
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,
                read_message_history=True,
            )

        # Opener keeps send access
        opener = guild.get_member(self.opener_id)
        if opener:
            overwrites[opener] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )

        await channel.edit(overwrites=overwrites)

        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)

        await channel.send(
            f"🙋 {interaction.user.mention} has claimed this ticket."
        )

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket_close",
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can close tickets.", ephemeral=True
            )

        channel = interaction.channel
        guild = interaction.guild
        staff_role = guild.get_role(TICKET_STAFF_ROLE_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
            ),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,
                read_message_history=True,
            )

        await channel.edit(
            overwrites=overwrites,
            reason=f"Ticket closed by {interaction.user}",
        )

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        await channel.send(
            f"🔒 This ticket has been closed by {interaction.user.mention}."
        )


class TicketPanelView(discord.ui.View):
    def __init__(self, options: list, custom_messages: dict):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown(options, custom_messages))


@tree.command(name="ticket", description="Post a ticket panel (admin only)")
@app_commands.describe(
    title="Panel title",
    description="Panel description",
    drop1="First dropdown option (required)",
    msg1="Custom message shown when drop1 ticket is opened (optional)",
    drop2="Second dropdown option (optional)",
    msg2="Custom message shown when drop2 ticket is opened (optional)",
    drop3="Third dropdown option (optional)",
    msg3="Custom message shown when drop3 ticket is opened (optional)",
    drop4="Fourth dropdown option (optional)",
    msg4="Custom message shown when drop4 ticket is opened (optional)",
    drop5="Fifth dropdown option (optional)",
    msg5="Custom message shown when drop5 ticket is opened (optional)",
    banner="Banner image URL (optional)",
)
@app_commands.checks.has_permissions(administrator=True)
async def ticket_command(
    interaction: discord.Interaction,
    title: str,
    description: str,
    drop1: str,
    msg1: str = None,
    drop2: str = None,
    msg2: str = None,
    drop3: str = None,
    msg3: str = None,
    drop4: str = None,
    msg4: str = None,
    drop5: str = None,
    msg5: str = None,
    banner: str = None,
):
    options = [o for o in [drop1, drop2, drop3, drop4, drop5] if o]

    # Map each dropdown label to its custom message
    custom_messages = {}
    for label, msg in zip([drop1, drop2, drop3, drop4, drop5], [msg1, msg2, msg3, msg4, msg5]):
        if label and msg:
            custom_messages[label] = msg

    embed = discord.Embed(
        title=title,
        description=description,
        color=EMBED_COLOR,
    )

    view = TicketPanelView(options=options, custom_messages=custom_messages)

    await interaction.response.defer(ephemeral=True)

    if banner:
        async with aiohttp.ClientSession() as session:
            try:
                data, filename = await fetch_image_bytes(banner, session)
                buf = io.BytesIO(data)
                buf.seek(0)
                f = discord.File(fp=buf, filename=filename)
                embed.set_image(url=f"attachment://{filename}")
                await interaction.channel.send(file=f, embed=embed, view=view)
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Failed to fetch banner: {e}", ephemeral=True
                )
                return
    else:
        await interaction.channel.send(embed=embed, view=view)

    await interaction.followup.send("✅ Ticket panel posted.", ephemeral=True)


@ticket_command.error
async def ticket_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ You don't have permission to use this.", ephemeral=True
        )


# ======================
# GLOBAL ERROR HANDLER
# ======================

@bot.event
async def on_command_error(ctx, error):
    ignored = (
        commands.MissingRequiredArgument,
        commands.BadArgument,
        commands.CommandNotFound,
        commands.CheckFailure,
        commands.MissingPermissions,
    )
    if isinstance(error, ignored):
        return
    raise error


# ======================
# STARTUP
# ======================

@bot.event
async def on_ready():
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="Priority One"),
    )
    try:
        guild = discord.Object(id=1091573463979925576)
        # Clear any old global commands (removes duplicates)
        tree.clear_commands(guild=None)
        await tree.sync(guild=None)
        # Sync guild-specific commands instantly
        synced = await tree.sync(guild=guild)
        print(f"Synced {len(synced)} slash command(s) to guild")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print(f"Logged in as {bot.user}")


if __name__ == "__main__":
    bot.run(TOKEN)
