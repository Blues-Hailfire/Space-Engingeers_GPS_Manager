# Space Engineers GPS Manager

A locally-hosted Discord bot for managing Space Engineers GPS coordinates within a faction. GPS points are stored per-channel in a local SQLite database and can be searched, filtered, visualised on an interactive 3D map, and bulk-removed.

---

## Requirements

- Python 3.8+
- `discord.py >= 2.3.0`
- A Discord bot token in `DiscordToken.txt`

Run `setup.py` to create the virtual environment and install dependencies.

---

## Setup

1. Create a Discord bot and place its token in `DiscordToken.txt`.
2. Run `python setup.py` to initialise the virtual environment.
3. Start the bot: `python VectorHandler.py`.
4. In your target Discord channel, run `/bind` (requires Administrator) to lock the bot to that channel.

---

## Commands

### `/bind`
Binds the bot to the current channel. All other commands will only work in the bound channel.

> Requires **Administrator** permission.

---

### `/add_gps`
Adds one or more GPS points to the channel's database.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `gps_string` | string | Yes | One or more GPS points in Space Engineers format: `GPS:Name:X:Y:Z:Color:` |

- Accepts multiple points separated by spaces or newlines.
- Supports optional ARGB hex colours (`#AARRGGBB`).

---

### `/search_gps`
Searches the channel's GPS points with optional keyword and distance filtering.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `search_string` | string | No | Keyword to match against point names (case-insensitive) |
| `reference_gps` | string | No | A GPS point used as the distance origin (`GPS:Name:X:Y:Z:Color:`) |
| `distance_km` | float | No | Filters out points beyond this distance (km) from the reference |

**Behaviour:**
- No parameters → returns all points.
- `search_string` only → returns matching points.
- `reference_gps` + `distance_km` → returns points within range, sorted nearest first.
- `reference_gps` + `search_string` → returns matches sorted by distance from reference.

---

### `/map`
Generates an interactive 3D HTML map of all GPS points in the channel and sends it as a downloadable attachment.

The map renders in any modern browser with no dependencies — open the file locally. Features include:

- **3D globe view** with OrbitControls (pan, zoom, rotate)
- **Animated pulse rings** that emit from the selected point at a frequency matching its glow, with ring radius scaling to camera zoom
- **Distance measurement** mode with on-screen readout
- **Sidebar** with searchable, filterable point list — collapses to expand the canvas
- **Point detail panel** showing coordinates and tags
- **Hit detection** — the pulse wave briefly illuminates points it passes through
- Click a selected point (on the globe or in the sidebar) to deselect it

---

### `/remove_gps_by_index_range`
Removes a contiguous range of GPS points by their 1-based index.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `start_index` | integer | Yes | First index to remove (inclusive) |
| `end_index` | integer | Yes | Last index to remove (inclusive) |

---

## Project Structure

```
VectorHandler.py        # Bot entry point — all commands and database logic
templates/map.html      # Interactive 3D map template (Three.js)
setup.py                # Environment setup script
DiscordToken.txt        # Bot token (not committed)
gps.db                  # SQLite database (auto-created on first run)
```

---

## Database

SQLite (`gps.db`) with two tables:

- **`gps_points`** — GPS coordinates scoped to guild + channel.
- **`guild_bindings`** — Maps each guild to its single bound channel.
