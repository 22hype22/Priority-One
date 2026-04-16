import io
import re
import asyncio
import typing
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import os
import traceback
import datetime
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import wavelink
from aiohttp import web

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
UPDATES_FILE = "game_updates.json"
EMBED_COLOR = discord.Color.from_str("#181818")

TICKET_STAFF_ROLE_ID = 1126332043517767690

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID = os.getenv("GIST_ID")

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
))

LAVALINK_NODE_CONFIGS = [
    {"uri": "https://lavalinkv4.serenetia.com", "password": "https://seretia.link/discord"},
    {"uri": "https://lavalink.jirayu.net", "password": "youshallnotpass"},
]

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

async def load_updates_async():
    if not GITHUB_TOKEN or not GIST_ID:
        return []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.github.com/gists/{GIST_ID}",
                headers={"Authorization": f"token {GITHUB_TOKEN}"}
            ) as resp:
                data = await resp.json()
                content = data["files"]["game_updates.json"]["content"]
                return json.loads(content)
    except Exception as e:
        print(f"Failed to load updates: {e}")
        return []

async def save_updates_async(data):
    if not GITHUB_TOKEN or not GIST_ID:
        return
    try:
        async with aiohttp.ClientSession() as session:
            await session.patch(
                f"https://api.github.com/gists/{GIST_ID}",
                headers={"Authorization": f"token {GITHUB_TOKEN}"},
                json={"files": {"game_updates.json": {"content": json.dumps(data, indent=2)}}}
            )
    except Exception as e:
        print(f"Failed to save updates: {e}")

async def fetch_image_bytes(url: str, session: aiohttp.ClientSession):
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ValueError(f"HTTP {resp.status} when fetching image")
        data = await resp.read()
        filename = url.split("?")[0].split("/")[-1] or "image.png"
        if "." not in filename:
            filename += ".png"
        return data, filename


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

class SayModeChoice(str, discord.Enum):
    normal = "normal"
    embed = "embed"

@tree.command(name="say", description="Post a message as the bot (admin only)")
@app_commands.describe(
    mode="Choose Normal or Embed",
    title="Title of the message",
    author="Author name (embed only)",
    desc="Main body text",
    footer="Footer text (embed only)",
    banner="Attach an image file for the banner",
    banner_url="Or paste a banner image URL instead",
)
async def say_command(
    interaction: discord.Interaction,
    mode: SayModeChoice = SayModeChoice.normal,
    title: str = None,
    author: str = None,
    desc: str = None,
    footer: str = None,
    banner: discord.Attachment = None,
    banner_url: str = None,
):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "❌ You don't have permission to use this.", ephemeral=True
        )

    use_embed = mode == SayModeChoice.embed
    channel = interaction.channel

    await interaction.response.defer(ephemeral=True)

    banner_file = None
    async with aiohttp.ClientSession() as session:
        if banner:
            try:
                data, filename = await fetch_image_bytes(banner.url, session)
                buf = io.BytesIO(data)
                buf.seek(0)
                banner_file = discord.File(fp=buf, filename=filename)
            except Exception as e:
                return await interaction.followup.send(
                    f"❌ Failed to fetch banner attachment: {e}", ephemeral=True
                )
        elif banner_url:
            try:
                data, filename = await fetch_image_bytes(banner_url, session)
                buf = io.BytesIO(data)
                buf.seek(0)
                banner_file = discord.File(fp=buf, filename=filename)
            except Exception as e:
                return await interaction.followup.send(
                    f"❌ Failed to fetch banner URL: {e}", ephemeral=True
                )

    try:
        if use_embed:
            embed = discord.Embed(color=EMBED_COLOR)
            if title:
                embed.title = title
            if desc:
                embed.description = desc
            if author:
                embed.set_author(name=author)
            if footer:
                embed.set_footer(text=footer)
            if banner_file:
                embed.set_image(url=f"attachment://{banner_file.filename}")
                if not any([title, desc, author, footer]):
                    embed.description = "\u200b"
                await channel.send(file=banner_file, embed=embed)
            else:
                await channel.send(embed=embed)
        else:
            lines = []
            if author:
                lines.append(f"**{author}**")
            if title:
                lines.append(f"**{title}**")
            if desc:
                lines.append(desc)
            if footer:
                lines.append(f"-# {footer}")

            text = "\n".join(lines) if lines else None
            if text:
                await channel.send(text)
            if banner_file:
                await channel.send(file=banner_file)

    except Exception as e:
        traceback.print_exc()
        return await interaction.followup.send(
            f"❌ Failed to post: `{type(e).__name__}: {str(e)[:180]}`", ephemeral=True
        )

    await interaction.followup.send("✅ Posted.", ephemeral=True)


# ======================
# TICKET SYSTEM
# ======================

class TicketDropdown(discord.ui.Select):
    def __init__(self, options: list, custom_messages: dict):
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

    @classmethod
    def from_message(cls, message: discord.Message):
        if not message.embeds:
            return None
        embed = message.embeds[0]
        if not embed.footer or not embed.footer.text:
            return None
        try:
            data = json.loads(embed.footer.text)
            options = data.get("options", [])
            custom_messages = data.get("messages", {})
            if not options:
                return None
            return cls(options=options, custom_messages=custom_messages)
        except Exception:
            return None

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        guild = interaction.guild
        user = interaction.user
        staff_role = guild.get_role(TICKET_STAFF_ROLE_ID)

        safe_name = re.sub(r"[^a-z0-9-]", "", user.name.lower().replace(" ", "-"))
        channel_name = f"ticket-{safe_name}"
        category_name = f"{category} Tickets"
        existing_category = discord.utils.get(guild.categories, name=category_name)
        if existing_category:
            existing = discord.utils.get(existing_category.text_channels, name=channel_name)
            if existing:
                return await interaction.response.send_message(
                    f"❌ You already have an open **{category}** ticket: {existing.mention}",
                    ephemeral=True,
                )

        tickets_category = discord.utils.get(guild.categories, name=category_name)
        if not tickets_category:
            try:
                tickets_category = await guild.create_category(
                    name=category_name,
                    reason="Auto-created for ticket system",
                )
            except discord.Forbidden:
                tickets_category = None

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
                topic=f"opener:{user.id}",
                reason=f"Ticket opened by {user} — {category}",
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to create channels.",
                ephemeral=True,
            )

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
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
        }

        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,
                read_message_history=True,
            )

        opener_id = self.opener_id
        if not opener_id and channel.topic and channel.topic.startswith("opener:"):
            try:
                opener_id = int(channel.topic.split("opener:")[1])
            except ValueError:
                pass

        opener = guild.get_member(opener_id) if opener_id else None
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

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        await channel.send(
            f"🔒 This ticket has been closed by {interaction.user.mention}. Deleting in 5 seconds..."
        )
        await asyncio.sleep(5)
        await channel.delete(reason=f"Ticket closed by {interaction.user}")

        guild = interaction.guild
        parent = channel.category
        if parent and parent.name.endswith(" Tickets") and len(parent.channels) == 0:
            await parent.delete(reason="No open tickets remaining")


class TicketPanelView(discord.ui.View):
    def __init__(self, options: list, custom_messages: dict):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown(options, custom_messages))


@tree.command(name="ticket", description="Post a ticket panel (admin only)")
@app_commands.describe(
    title="Panel title",
    body="Panel description text",
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
async def ticket_command(
    interaction: discord.Interaction,
    title: str,
    body: str,
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
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "❌ You don't have permission to use this.", ephemeral=True
        )
    options = [o for o in [drop1, drop2, drop3, drop4, drop5] if o]

    custom_messages = {}
    for label, msg in zip([drop1, drop2, drop3, drop4, drop5], [msg1, msg2, msg3, msg4, msg5]):
        if label and msg:
            custom_messages[label] = msg

    footer_data = json.dumps({"options": options, "messages": custom_messages})

    embed = discord.Embed(
        title=title,
        description=body,
        color=EMBED_COLOR,
    )
    embed.set_footer(text=footer_data)

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


async def restore_ticket_panels(bot: commands.Bot):
    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                async for message in channel.history(limit=50):
                    if message.author == guild.me and message.embeds:
                        embed = message.embeds[0]
                        if embed.footer and embed.footer.text:
                            try:
                                data = json.loads(embed.footer.text)
                                options = data.get("options", [])
                                custom_messages = data.get("messages", {})
                                if options:
                                    view = TicketPanelView(
                                        options=options,
                                        custom_messages=custom_messages,
                                    )
                                    bot.add_view(view, message_id=message.id)
                            except Exception:
                                pass
            except Exception:
                pass


@ticket_command.error
async def ticket_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await interaction.response.send_message(
        f"❌ Something went wrong: {error}", ephemeral=True
    )


# ======================
# GAME UPDATE SYSTEM
# ======================

class UpdateEntryModal(discord.ui.Modal, title="Add Update Entry"):
    def __init__(self, update_type: str, entries: list, view: "UpdateBuilderView"):
        super().__init__()
        self.update_type = update_type
        self.entries = entries
        self.builder_view = view

    text = discord.ui.TextInput(
        label="Update description",
        placeholder="Describe the update...",
        max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        self.entries.append({
            "type": self.update_type,
            "text": self.text.value.strip(),
        })
        await interaction.response.edit_message(
            content=self.builder_view.preview(),
            view=self.builder_view,
        )


class UpdateBuilderView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.entries: list[dict] = []

    def preview(self) -> str:
        if not self.entries:
            return "**No entries yet.** Add some updates below."
        lines = ["**Preview:**"]
        for e in self.entries:
            emoji = {"New": "🟡", "Fix": "🟢", "Patch": "🟠"}.get(e["type"], "⚪")
            lines.append(f"{emoji} **{e['type']}** — {e['text']}")
        return "\n".join(lines)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your update builder.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="+ New", style=discord.ButtonStyle.secondary, row=0)
    async def add_new(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = UpdateEntryModal("New", self.entries, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="+ Fix", style=discord.ButtonStyle.secondary, row=0)
    async def add_fix(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = UpdateEntryModal("Fix", self.entries, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="+ Patch", style=discord.ButtonStyle.secondary, row=0)
    async def add_patch(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = UpdateEntryModal("Patch", self.entries, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="↩ Undo Last", style=discord.ButtonStyle.danger, row=1)
    async def undo_last(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.entries:
            self.entries.pop()
        await interaction.response.edit_message(
            content=self.preview(),
            view=self,
        )

    @discord.ui.button(label="✅ Post Update", style=discord.ButtonStyle.success, row=1)
    async def post_update(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.entries:
            return await interaction.response.send_message(
                "❌ Add at least one entry first.", ephemeral=True
            )

        order = {"New": 0, "Fix": 1, "Patch": 2}
        sorted_entries = sorted(self.entries, key=lambda e: order.get(e["type"], 99))

        today = datetime.date.today().strftime("%B %-d, %Y")

        updates = await load_updates_async()
        existing = next((u for u in updates if u["date"] == today), None)
        if existing:
            existing["fixes"].extend(sorted_entries)
            existing["fixes"] = sorted(
                existing["fixes"], key=lambda e: order.get(e["type"], 99)
            )
        else:
            updates.insert(0, {
                "date": today,
                "fixes": sorted_entries,
            })

        await save_updates_async(updates)

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="✅ Update posted!", view=self)

        embed = discord.Embed(
            title=f"🛠️ SkyHarvest Update — {today}",
            color=discord.Color.from_str("#ec9206"),
        )
        lines = []
        for e in sorted_entries:
            lines.append(f"- `{e['type'].upper()}` | {e['text']}")
        embed.description = "\n".join(lines)
        embed.set_footer(text=f"Posted by {interaction.user.display_name}")

        await interaction.channel.send(embed=embed)


@tree.command(name="gameupdate", description="Post a SkyHarvest game update (admin only)")
async def gameupdate_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "❌ You don't have permission to use this.", ephemeral=True
        )
    view = UpdateBuilderView(author_id=interaction.user.id)
    await interaction.response.send_message(
        content="**No entries yet.** Use the buttons below to add updates.",
        view=view,
        ephemeral=True,
    )


@tree.command(name="clearupdate", description="Remove a specific update entry from the game (admin only)")
@app_commands.describe(
    date="The date of the update e.g. April 11, 2026",
    text="The exact text of the entry to remove",
)
async def clearupdate_command(
    interaction: discord.Interaction,
    date: str,
    text: str,
):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "❌ You don't have permission to use this.", ephemeral=True
        )

    updates = await load_updates_async()
    found = False

    for group in updates:
        if group["date"].lower() == date.lower():
            before = len(group["fixes"])
            group["fixes"] = [f for f in group["fixes"] if f["text"].lower() != text.lower()]
            if len(group["fixes"]) < before:
                found = True
            break

    updates = [g for g in updates if g["fixes"]]
    await save_updates_async(updates)

    if found:
        await interaction.response.send_message(
            f"✅ Removed entry from **{date}**. It will no longer show in game.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "❌ Couldn't find that entry. Check the date and text match exactly.", ephemeral=True
        )


# ======================
# HTTP SERVER FOR ROBLOX
# ======================

async def handle_updates(request):
    updates = await load_updates_async()
    return web.json_response(updates)

async def start_http_server():
    app = web.Application()
    app.router.add_get("/updates", handle_updates)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("HTTP server running on port 8080")


# ======================
# MUSIC SYSTEM
# ======================

music_history: dict[int, list[wavelink.Playable]] = {}

def get_history(guild_id: int) -> list:
    if guild_id not in music_history:
        music_history[guild_id] = []
    return music_history[guild_id]


async def get_spotify_tracks(playlist_url: str) -> list[str]:
    loop = asyncio.get_event_loop()
    try:
        playlist_id = playlist_url.split("/playlist/")[-1].split("?")[0]
        tracks = []
        offset = 0
        while True:
            results = await loop.run_in_executor(
                None,
                lambda o=offset: sp.playlist_tracks(playlist_id, offset=o, limit=50)
            )
            items = results.get("items", [])
            if not items:
                break
            for item in items:
                track = item.get("track")
                if track:
                    name = track.get("name", "")
                    artists = ", ".join(a["name"] for a in track.get("artists", []))
                    tracks.append(f"{name} {artists}")
            if not results.get("next"):
                break
            offset += 50
        return tracks
    except Exception as e:
        print(f"Spotify error: {e}")
        return []


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    player = payload.player
    if player and player.guild:
        hist = get_history(player.guild.id)
        hist.append(payload.track)


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player = payload.player
    if not player:
        return
    if payload.reason == "finished":
        if player.queue.is_empty:
            await asyncio.sleep(1)
            if not player.playing:
                await player.disconnect()
        else:
            next_track = player.queue.get()
            await player.play(next_track)


@tree.command(name="play", description="Play a Spotify playlist or search for a song")
@app_commands.describe(query="Spotify playlist URL or song name")
async def play_command(interaction: discord.Interaction, query: str):
    if not interaction.user.voice:
        return await interaction.response.send_message(
            "❌ You need to be in a voice channel.", ephemeral=True
        )

    await interaction.response.defer()

    guild = interaction.guild
    voice_channel = interaction.user.voice.channel

    player = typing.cast(wavelink.Player, guild.voice_client)
    if player is None:
        try:
            player = await asyncio.wait_for(
                voice_channel.connect(cls=wavelink.Player),
                timeout=20.0
            )
        except asyncio.TimeoutError:
            return await interaction.followup.send(
                "❌ Timed out connecting to voice channel. Try again."
            )
        except Exception as e:
            return await interaction.followup.send(f"❌ Failed to join voice channel: {e}")
    elif player.channel != voice_channel:
        await player.move_to(voice_channel)

    if "spotify.com/playlist" in query:
        await interaction.followup.send("🔍 Fetching Spotify playlist...")
        track_names = await get_spotify_tracks(query)
        if not track_names:
            return await interaction.followup.send(
                "❌ Couldn't load that playlist. Make sure it's public."
            )

        await interaction.followup.send(f"⏳ Searching **{len(track_names)}** tracks...")

        loaded = 0
        for name in track_names:
            try:
                results = await wavelink.Playable.search(name)
                if results:
                    await player.queue.put_wait(results[0])
                    loaded += 1
            except Exception:
                pass

        await interaction.followup.send(f"✅ Added **{loaded}** tracks to the queue.")

        if not player.playing and not player.queue.is_empty:
            track = player.queue.get()
            await player.play(track)

    else:
        try:
            results = await wavelink.Playable.search(query)
        except Exception as e:
            return await interaction.followup.send(f"❌ Search failed: {e}")

        if not results:
            return await interaction.followup.send("❌ Couldn't find that song.")

        track = results[0]
        if player.playing:
            await player.queue.put_wait(track)
            await interaction.followup.send(f"✅ Added **{track.title}** to the queue.")
        else:
            await player.play(track)
            await interaction.followup.send(f"🎵 Now playing: **{track.title}**")


@tree.command(name="skip", description="Skip the current song")
async def skip_command(interaction: discord.Interaction):
    player = typing.cast(wavelink.Player, interaction.guild.voice_client)
    if not player or not player.playing:
        return await interaction.response.send_message(
            "❌ Nothing is playing.", ephemeral=True
        )
    await player.skip()
    await interaction.response.send_message("⏭️ Skipped.")


@tree.command(name="previous", description="Play the previous song")
async def previous_command(interaction: discord.Interaction):
    guild = interaction.guild
    player = typing.cast(wavelink.Player, guild.voice_client)

    if not player:
        return await interaction.response.send_message(
            "❌ Not in a voice channel.", ephemeral=True
        )

    hist = get_history(guild.id)
    if len(hist) < 2:
        return await interaction.response.send_message(
            "❌ No previous song.", ephemeral=True
        )

    prev = hist[-2]
    music_history[guild.id] = hist[:-2]
    await player.play(prev)
    await interaction.response.send_message(f"⏮️ Going back to **{prev.title}**.")


@tree.command(name="stop", description="Stop music and disconnect")
async def stop_command(interaction: discord.Interaction):
    player = typing.cast(wavelink.Player, interaction.guild.voice_client)

    if not player:
        return await interaction.response.send_message(
            "❌ Not in a voice channel.", ephemeral=True
        )

    music_history[interaction.guild.id] = []
    player.queue.clear()
    await player.stop()
    await player.disconnect()
    await interaction.response.send_message("⏹️ Stopped and disconnected.")


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
        activity=discord.Game(name="Keeping an eye on the Oversite community"),
    )
    bot.add_view(TicketActionView())
    await restore_ticket_panels(bot)
    await start_http_server()

    try:
        nodes = [wavelink.Node(uri=c["uri"], password=c["password"]) for c in LAVALINK_NODE_CONFIGS]
        await wavelink.Pool.connect(nodes=nodes, client=bot)
        print("Connected to Lavalink")
    except Exception as e:
        print(f"Lavalink connection failed: {e}")

    try:
        print(f"Commands in tree: {[c.name for c in tree.get_commands()]}")
        synced = await tree.sync()
        print(f"Synced {len(synced)} slash command(s) globally")
    except Exception as e:
        traceback.print_exc()
        print(f"Failed to sync commands: {e}")
    print(f"Logged in as {bot.user}")


if __name__ == "__main__":
    bot.run(TOKEN)
