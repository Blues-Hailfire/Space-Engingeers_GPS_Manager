import discord
from discord.ext import commands
import io
import json
import math
import os
import sqlite3
from contextlib import contextmanager

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())
GPSBankInterface = 1059965274738151475

DB_PATH = "gps.db"
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
MAP_TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, "map.html")


DEFAULT_GPS_COLOR = "#FFFFFFFF"


class Vector3D:
    def __init__(self, name, x, y, z, color=DEFAULT_GPS_COLOR):
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.color = color or DEFAULT_GPS_COLOR

    def __str__(self):
        return f"GPS:{self.name}:{self.x}:{self.y}:{self.z}:{self.color}:"


def parse_gps_data(gps_string):
    try:
        data = gps_string.replace("GPS:", "").replace("\n", "").strip(":")
        parts = data.split(":")
        name = parts[0]
        x = float(parts[1])
        y = float(parts[2])
        z = float(parts[3])
        color = parts[4] if len(parts) > 4 and parts[4] else DEFAULT_GPS_COLOR
    except (IndexError, ValueError) as e:
        raise Exception("Not A Valid GPS point") from e

    return Vector3D(name, x, y, z, color)


def euclidean_distance(v1, v2):
    return math.sqrt((v1.x - v2.x) ** 2 + (v1.y - v2.y) ** 2 + (v1.z - v2.z) ** 2)


@contextmanager
def db():
    parent = os.path.dirname(os.path.abspath(DB_PATH))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    fresh = not os.path.exists(DB_PATH)
    if fresh:
        print(f"[db] no database found, creating new one at {os.path.abspath(DB_PATH)}")
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gps_points (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                name       TEXT    NOT NULL,
                x          REAL    NOT NULL,
                y          REAL    NOT NULL,
                z          REAL    NOT NULL,
                color      TEXT    NOT NULL DEFAULT '#FFFFFFFF'
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_gps_guild_channel
            ON gps_points (guild_id, channel_id, id)
        """)
        # Add color column if upgrading from a pre-color schema.
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(gps_points)")}
        if "color" not in existing:
            conn.execute(
                "ALTER TABLE gps_points ADD COLUMN color TEXT NOT NULL DEFAULT '#FFFFFFFF'"
            )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_bindings (
                guild_id   INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS migrated_files (
                path       TEXT PRIMARY KEY,
                migrated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)


def migrate_legacy_files(root_dir="./guild_data"):
    """Import any legacy ./guild_data/{guild_id}/{channel_id}_GPS_Data.txt
    files into the SQLite database. Each file is imported at most once,
    tracked via the migrated_files table."""
    if not os.path.isdir(root_dir):
        return

    imported_files = 0
    imported_points = 0
    for guild_name in os.listdir(root_dir):
        guild_path = os.path.join(root_dir, guild_name)
        if not os.path.isdir(guild_path):
            continue
        try:
            guild_id = int(guild_name)
        except ValueError:
            continue

        for fname in os.listdir(guild_path):
            if not fname.endswith("_GPS_Data.txt"):
                continue
            channel_str = fname[:-len("_GPS_Data.txt")]
            try:
                channel_id = int(channel_str)
            except ValueError:
                continue

            full_path = os.path.abspath(os.path.join(guild_path, fname))

            with db() as conn:
                already = conn.execute(
                    "SELECT 1 FROM migrated_files WHERE path = ?",
                    (full_path,),
                ).fetchone()
                if already:
                    continue

                rows = []
                try:
                    with open(full_path, "r") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                v = parse_gps_data(line)
                                rows.append((guild_id, channel_id, v.name, v.x, v.y, v.z, v.color))
                            except Exception as e:
                                print(f"[migrate] skipping bad line in {full_path}: {e}")
                except OSError as e:
                    print(f"[migrate] could not read {full_path}: {e}")
                    continue

                if rows:
                    conn.executemany(
                        "INSERT INTO gps_points (guild_id, channel_id, name, x, y, z, color) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        rows,
                    )
                conn.execute(
                    "INSERT INTO migrated_files (path) VALUES (?)",
                    (full_path,),
                )
                imported_files += 1
                imported_points += len(rows)
                print(f"[migrate] imported {len(rows)} points from {full_path}")

    if imported_files:
        print(f"[migrate] done: {imported_points} points across {imported_files} file(s)")


def load_vectors(guild_id, channel_id):
    with db() as conn:
        rows = conn.execute(
            "SELECT id, name, x, y, z, color FROM gps_points "
            "WHERE guild_id = ? AND channel_id = ? ORDER BY id",
            (guild_id, channel_id),
        ).fetchall()
    return [(i + 1, r["id"], Vector3D(r["name"], r["x"], r["y"], r["z"], r["color"]))
            for i, r in enumerate(rows)]


def add_vector(guild_id, channel_id, vector):
    with db() as conn:
        conn.execute(
            "INSERT INTO gps_points (guild_id, channel_id, name, x, y, z, color) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (guild_id, channel_id, vector.name, vector.x, vector.y, vector.z, vector.color),
        )


def remove_vectors_by_index_range(guild_id, channel_id, start_index, end_index):
    vectors = load_vectors(guild_id, channel_id)
    if start_index < 1 or end_index > len(vectors) or start_index > end_index:
        return False
    ids_to_delete = [row_id for idx, row_id, _ in vectors
                     if start_index <= idx <= end_index]
    with db() as conn:
        conn.executemany(
            "DELETE FROM gps_points WHERE id = ?",
            [(rid,) for rid in ids_to_delete],
        )
    return True


def get_bind_channel(guild_id):
    with db() as conn:
        row = conn.execute(
            "SELECT channel_id FROM guild_bindings WHERE guild_id = ?",
            (guild_id,),
        ).fetchone()
    return row["channel_id"] if row else None


def set_bind_channel(guild_id, channel_id):
    with db() as conn:
        conn.execute(
            "INSERT INTO guild_bindings (guild_id, channel_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id",
            (guild_id, channel_id),
        )


async def reject_if_not_bound(interaction: discord.Interaction) -> bool:
    """Return True (and send a rejection message) if this command should be blocked.
    Commands are blocked unless an admin has bound a channel via /bind and the
    command is being used in that channel."""
    bound = get_bind_channel(interaction.guild.id)
    if bound is None:
        await interaction.response.send_message(
            "No channel is bound for this server. An administrator must run `/bind` "
            "in the channel where this bot should operate before any commands can be used.",
            ephemeral=True,
        )
        return True
    if interaction.channel.id != bound:
        await interaction.response.send_message(
            "This command can only be used in the bound channel.",
            ephemeral=True,
        )
        return True
    return False


@bot.event
async def on_ready():
    init_db()
    print(f"We have logged in as {bot.user}")
    for guild in bot.guilds:
        print(f"Server Name: {guild.name}, Server ID: {guild.id}")
    await bot.tree.sync()


@bot.tree.command(name="search_gps", description="Search GPS points with various filters.")
async def search_gps(interaction: discord.Interaction, search_string: str = None, reference_gps: str = None, distance_km: float = None):
    """Search for GPS points with optional filters: reference GPS and distance."""
    if await reject_if_not_bound(interaction):
        return

    vectors = load_vectors(interaction.guild.id, interaction.channel.id)

    if search_string is None and reference_gps is None and distance_km is None:
        if vectors:
            response = "**All GPS Points:**\n```"
            for index, _, vector in vectors:
                response += f"{index}: {vector}\n"
            response += "```"
            await interaction.response.send_message(response)
        else:
            await interaction.response.send_message("No GPS points found.")
        return

    if reference_gps:
        try:
            reference_point = parse_gps_data(reference_gps)
        except Exception as e:
            await interaction.response.send_message(f"Invalid reference GPS point: {str(e)}")
            return

        if distance_km is not None:
            nearby = [(v, euclidean_distance(reference_point, v))
                      for _, _, v in vectors]
            nearby = [(v, d) for v, d in nearby if d <= distance_km * 1000]
            if nearby:
                response = f"**GPS Points within {distance_km} Km of {reference_point.name}:**\n```"
                for vector, dist in nearby:
                    response += f"{vector.name}: {vector} (Distance: {dist/1000:.2f} Km)\n"
                response += "```"
                await interaction.response.send_message(response)
            else:
                await interaction.response.send_message(f"No GPS points found within {distance_km} Km of {reference_point.name}.")
            return

        results = [(idx, v, euclidean_distance(reference_point, v))
                   for idx, _, v in vectors
                   if search_string and search_string.lower() in v.name.lower()]
        results.sort(key=lambda x: x[2])
        if results:
            response = f"**Closest Points to {reference_point.name} containing '{search_string}':**\n```"
            for index, vector, distance in results:
                response += f"{index}: {vector}, Distance: {(distance / 1000):.2f} Km\n"
            response += "```"
            await interaction.response.send_message(response)
        else:
            await interaction.response.send_message(f"No GPS points found containing '{search_string}' near {reference_point.name}.")
        return

    matches = [(idx, v) for idx, _, v in vectors
               if search_string.lower() in v.name.lower()]
    if matches:
        response = f"**Results for '{search_string}':**\n```"
        for index, vector in matches:
            response += f"{index}: {vector}\n"
        response += "```"
        await interaction.response.send_message(response)
    else:
        await interaction.response.send_message(f"No GPS points found containing '{search_string}'.")


@bot.tree.command(name="add_gps", description="Add a GPS point to the storage.")
async def add_gps(interaction: discord.Interaction, gps_string: str):
    """Add a GPS point to the storage."""
    if await reject_if_not_bound(interaction):
        return

    gpslist = gps_string.split("GPS:")
    for gps in gpslist:
        if gps == '':
            continue
        try:
            vector = parse_gps_data(gps)
            add_vector(interaction.guild.id, interaction.channel.id, vector)
            await interaction.channel.send("Identified Point: " + str(vector))
        except Exception as e:
            await interaction.channel.send(f"Error adding GPS point: {str(e)}\nPoint: {gps}")
    await interaction.response.send_message("Succesfully stashed all identified GPS Points.")


@bot.tree.command(name="bind", description="Bind the bot to respond only in this channel.")
@commands.has_permissions(administrator=True)
async def bind(interaction: discord.Interaction):
    set_bind_channel(interaction.guild.id, interaction.channel.id)
    await interaction.response.send_message(f"Bot is now bound to this channel: {interaction.channel.name}")


@bind.error
async def bind_error(interaction: discord.Interaction, error: commands.CommandError):
    if isinstance(error, commands.MissingPermissions):
        await interaction.response.send_message("You do not have permission to run this command.", ephemeral=True)


def argb_to_css_hex(color: str) -> str:
    """Space Engineers GPS color is #AARRGGBB. CSS uses #RRGGBB."""
    if not color:
        return "#ffffff"
    c = color.lstrip("#")
    if len(c) == 8:
        return "#" + c[2:]
    if len(c) == 6:
        return "#" + c
    return "#ffffff"


def build_map_html(points, title: str) -> str:
    payload = [
        {
            "name": v.name,
            "x": v.x,
            "y": v.y,
            "z": v.z,
            "color": argb_to_css_hex(v.color),
        }
        for _, _, v in points
    ]
    data_json = json.dumps(payload)
    safe_title = title.replace("<", "&lt;").replace(">", "&gt;")

    with open(MAP_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    return (template
            .replace("{{POINTS_JSON}}", data_json)
            .replace("{{POINT_COUNT}}", str(len(payload)))
            .replace("{{TITLE}}", safe_title))


@bot.tree.command(name="map", description="Render an interactive 3D HTML map of all GPS points in this channel.")
async def map_gps(interaction: discord.Interaction):
    if await reject_if_not_bound(interaction):
        return
    points = load_vectors(interaction.guild.id, interaction.channel.id)
    if not points:
        await interaction.response.send_message("No GPS points in this channel to map.")
        return

    title = f"#{interaction.channel.name}"
    html = build_map_html(points, title)
    buf = io.BytesIO(html.encode("utf-8"))
    file = discord.File(buf, filename=f"gps_map_{interaction.channel.id}.html")
    await interaction.response.send_message(
        f"Rendered {len(points)} point(s). Open the attached HTML in a browser.",
        file=file,
    )


@bot.tree.command(name="remove_gps_by_index_range", description="Remove GPS points between a range of indices (inclusive).")
async def remove_gps_range(interaction: discord.Interaction, start_index: int, end_index: int):
    """Remove GPS points between a range of indices (inclusive)."""
    if await reject_if_not_bound(interaction):
        return
    if remove_vectors_by_index_range(interaction.guild.id, interaction.channel.id, start_index, end_index):
        await interaction.response.send_message(f"Removed GPS points from index {start_index} to {end_index}.")
    else:
        await interaction.response.send_message(f"Invalid index range: {start_index} to {end_index}")


init_db()
migrate_legacy_files()

# Load Discord Token
with open("DiscordToken.txt", "r") as file:
    TOKEN = file.read().strip()

bot.run(TOKEN)
