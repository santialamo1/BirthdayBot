import discord
from discord.ext import commands, tasks
from pymongo import MongoClient
from datetime import datetime
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Variables de entorno desde Railway (no uses .env en prod)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
GUILD_ID = int(os.getenv("GUILD_ID"))

client = MongoClient(MONGO_URI)
db = client["birthdaybot"]
birthdays = db["birthdays"]

@bot.event
async def on_ready():
    print(f"¡Bot activo como {bot.user}!")
    check_birthdays.start()

@bot.command()
async def addbirthday(ctx, date: str):
    """Agrega tu cumpleaños en formato DD-MM."""
    user_id = ctx.author.id
    is_admin = ctx.author.guild_permissions.administrator

    if not is_admin:
        existing = birthdays.find_one({"user_id": user_id})
        if existing:
            await ctx.reply("Ya registraste tu cumpleaños.")
            return

    try:
        datetime.strptime(date, "%d-%m")
    except ValueError:
        await ctx.reply("Formato inválido. Usá DD-MM.")
        return

    birthdays.insert_one({
        "user_id": user_id,
        "username": str(ctx.author),
        "date": date
    })

    await ctx.reply(f"Cumpleaños guardado para {date}.")

@bot.command()
@commands.has_permissions(administrator=True)
async def removebirthday(ctx, user: discord.User):
    """Solo admins: elimina un cumpleaños."""
    result = birthdays.delete_one({"user_id": user.id})
    if result.deleted_count:
        await ctx.reply(f"Cumpleaños de {user} eliminado.")
    else:
        await ctx.reply("Ese usuario no tiene cumpleaños registrado.")

@tasks.loop(hours=24)
async def check_birthdays():
    today = datetime.now().strftime("%d-%m")
    guild = bot.get_guild(GUILD_ID)

    channel_chat = discord.utils.get(guild.text_channels, name="chat")
    channel_cumples = discord.utils.get(guild.text_channels, name="cumpleaños")

    if not channel_chat or not channel_cumples:
        print("No se encontraron los canales.")
        return

    celebrants = list(birthdays.find({"date": today}))

    if celebrants:
        for user_data in celebrants:
            user_id = user_data["user_id"]
            await channel_chat.send(f"🎉 ¡Feliz cumpleaños, <@{user_id}>! Que tengas un gran día.")
    
    # Actualizar lista en el canal cumpleaños
    all_birthdays = birthdays.find().sort("date", 1)
    message = "**🎂 Lista de cumpleaños del servidor:**
"
    for b in all_birthdays:
        message += f"<@{b['user_id']}> → {b['date']}
"

    pinned = await channel_cumples.pins()
    if pinned:
        await pinned[0].edit(content=message)
    else:
        msg = await channel_cumples.send(message)
        await msg.pin()

# Ejecutar bot
bot.run(DISCORD_TOKEN)
