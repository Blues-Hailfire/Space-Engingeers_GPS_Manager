import discord
from discord.ext import commands
import math
import os

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())
GPSBankInterface = 1059965274738151475

# Dictionary to store bind channel for each guild
bind_channels = {}

class Vector3D:
    def __init__(self, name, x, y, z):
        self.name = name
        self.x = x
        self.y = y
        self.z = z
    
    def __str__(self):
        return f"GPS:{self.name}:{self.x}:{self.y}:{self.z}:"

def create_dir_if_not_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def parse_gps_data(gps_string):
    try:
        data = gps_string.replace("GPS:", "").replace("\n", "").strip(":")
        parts = data.split(":")
        name = parts[0]
        x = float(parts[1])
        y = float(parts[2])
        z = float(parts[3])
    except (IndexError, ValueError) as e:
        raise Exception("Not A Valid GPS point") from e
    
    return Vector3D(name, x, y, z)

def save_vectors_to_file(vectors, filename):
    with open(filename, "w+") as f:
        f.write("\n".join(map(str, vectors)))

def load_vectors_from_file(filename):
    vectors = []
    try:
        with open(filename, "r") as f:
            for line in f:
                vectors.append(parse_gps_data(line))
    except FileNotFoundError:
        print(f"No file found: {filename}")
    return vectors

def euclidean_distance(v1, v2):
    return math.sqrt((v1.x - v2.x)**2 + (v1.y - v2.y)**2 + (v1.z - v2.z)**2)

def search_vectors_by_name(search_string, filename):
    vectors = load_vectors_from_file(filename)
    matching_vectors = [(i+1, vector) for i, vector in enumerate(vectors) if search_string.lower() in vector.name.lower()]
    return matching_vectors

def search_closest_vectors_by_name(search_string, reference_point, filename):
    matching_vectors = []
    vectors = load_vectors_from_file(filename)
    
    for i, vector in enumerate(vectors, start=1):
        if search_string.lower() in vector.name.lower():
            distance = euclidean_distance(reference_point, vector)
            matching_vectors.append((i, vector, distance))
    
    matching_vectors.sort(key=lambda x: x[2])
    return matching_vectors

def search_vectors_within_distance(reference_point, distance_km, filename):
    vectors = load_vectors_from_file(filename)
    nearby_vectors = []
    for vector in vectors:
        dist = euclidean_distance(reference_point, vector)
        if dist <= distance_km * 1000:  # Convert Km to meters
            nearby_vectors.append((vector, dist))
    return nearby_vectors

def remove_vectors_by_index_range(start_index, end_index, filename):
    """Remove vectors within the specified index range (inclusive) and update the file."""
    vectors = load_vectors_from_file(filename)
    
    # Check for valid index range
    if start_index < 1 or end_index > len(vectors) or start_index > end_index:
        return False
    
    # Remove the specified range of vectors
    del vectors[start_index-1:end_index]  # Adjust for 1-based indexing
    
    # Write the updated list of vectors back to the file
    save_vectors_to_file(vectors,filename)
    
    return True  # Return True indicating successful removal

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    for guild in bot.guilds:
        print(f"Server Name: {guild.name}, Server ID: {guild.id}")
        create_dir_if_not_exists(f"./guild_data/{guild.id}/")
    await bot.tree.sync()

@bot.tree.command(name="search_gps", description="Search GPS points with various filters.")
async def search_gps(interaction: discord.Interaction, search_string: str = None, reference_gps: str = None, distance_km: float = None):
    """Search for GPS points with optional filters: reference GPS and distance."""
    # Check if the command is invoked in the bound channel
    if interaction.guild.id in bind_channels and interaction.channel.id != bind_channels[interaction.guild.id]:
        await interaction.response.send_message("This command can only be used in the bound channel.", ephemeral=True)
        return

    filename = f"./guild_data/{interaction.guild.id}/{interaction.channel.id}_GPS_Data.txt"
    
    # If no search string is provided, return all GPS points
    if search_string is None and reference_gps is None and distance_km is None:
        vectors = load_vectors_from_file(filename)
        if vectors:
            response = "**All GPS Points:**\n```"
            for index, vector in enumerate(vectors, start=1):
                response += f"{index}: {vector}\n"
            response += "```"
            await interaction.response.send_message(response)
        else:
            await interaction.response.send_message("No GPS points found.")

    elif reference_gps:
        try:
            reference_point = parse_gps_data(reference_gps)
        except Exception as e:
            await interaction.response.send_message(f"Invalid reference GPS point: {str(e)}")
            return
        
        if distance_km is not None:
            nearby_vectors = search_vectors_within_distance(reference_point, distance_km, filename)
            if nearby_vectors:
                response = f"**GPS Points within {distance_km} Km of {reference_point.name}:**\n```"
                for vector, dist in nearby_vectors:
                    response += f"{vector.name}: {vector} (Distance: {dist/1000:.2f} Km)\n"
                response += "```"
                await interaction.response.send_message(response)
            else:
                await interaction.response.send_message(f"No GPS points found within {distance_km} Km of {reference_point.name}.")
        else:
            search_results = search_closest_vectors_by_name(search_string, reference_point, filename)
            if search_results:
                response = f"**Closest Points to {reference_point.name} containing '{search_string}':**\n```"
                for index, vector, distance in search_results:
                    response += f"{index}: {vector}, Distance: {(distance / 1000):.2f} Km\n"
                response += "```"
                await interaction.response.send_message(response)
            else:
                await interaction.response.send_message(f"No GPS points found containing '{search_string}' near {reference_point.name}.")
    else:
        search_results = search_vectors_by_name(search_string, filename)
        if search_results:
            response = f"**Results for '{search_string}':**\n```"
            for index, vector in search_results:
                response += f"{index}: {vector}\n"
            response += "```"
            await interaction.response.send_message(response)
        else:
            await interaction.response.send_message(f"No GPS points found containing '{search_string}'.")

@bot.tree.command(name="add_gps", description="Add a GPS point to the storage.")
async def add_gps(interaction: discord.Interaction, gps_string: str):
    """Add a GPS point to the storage."""
    # Check if the command is invoked in the bound channel
    if interaction.guild.id in bind_channels and interaction.channel.id != bind_channels[interaction.guild.id]:
        await interaction.response.send_message("This command can only be used in the bound channel.", ephemeral=True)
        return
    gpslist = gps_string.split("GPS:")
    filename= f"./guild_data/{interaction.guild.id}/{interaction.channel.id}_GPS_Data.txt"
    vectors = load_vectors_from_file(filename)
    for gps in gpslist:
        try:
            if gps == '':
                continue
            vector = parse_gps_data(gps)
            vectors.append(vector)
            await interaction.channel.send("Identified Point: " + str(vector))
        except Exception as e:
            await interaction.channel.send(f"Error adding GPS point: {str(e)}\nPoint: {gps}")
    save_vectors_to_file(vectors,filename)
    await interaction.response.send_message("Succesfully stashed all identified GPS Points.")

@bot.tree.command(name="bind", description="Bind the bot to respond only in this channel.")
@commands.has_permissions(administrator=True)
async def bind(interaction: discord.Interaction):
    bind_channels[interaction.guild.id] = interaction.channel.id
    await interaction.response.send_message(f"Bot is now bound to this channel: {interaction.channel.name}")

@bind.error
async def bind_error(interaction: discord.Interaction, error: commands.CommandError):
    if isinstance(error, commands.MissingPermissions):
        await interaction.response.send_message("You do not have permission to run this command.", ephemeral=True)

@bot.tree.command(name="remove_gps_by_index_range", description="Remove GPS points between a range of indices (inclusive).")
async def remove_gps_range(interaction: discord.Interaction, start_index: int, end_index: int):
    """Remove GPS points between a range of indices (inclusive)."""
    # Check if the command is invoked in the bound channel
    if interaction.guild.id in bind_channels and interaction.channel.id != bind_channels[interaction.guild.id]:
        await interaction.response.send_message("This command can only be used in the bound channel.", ephemeral=True)
        return
    filename= f"./guild_data/{interaction.guild.id}/{interaction.channel.id}_GPS_Data.txt"
    if remove_vectors_by_index_range(start_index, end_index, filename):
        await interaction.response.send_message(f"Removed GPS points from index {start_index} to {end_index}.")
    else:
        await interaction.response.send_message(f"Invalid index range: {start_index} to {end_index}")

# Load Discord Token
with open("DiscordToken.txt", "r") as file:
    TOKEN = file.read().strip()

bot.run(TOKEN)
