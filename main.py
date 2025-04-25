import discord
from discord.ext import commands, tasks
from pymongo import MongoClient
from datetime import datetime
import os
from collections import defaultdict

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

    channel_chat = discord.utils.get(guild.text_channels, name="┆💬┆𝖢𝗁𝖺𝗍")  # Canal de chat
    channel_cumples = discord.utils.get(guild.text_channels, name="┆🎉┆𝗖𝘂𝗺𝗽𝗹𝗲𝗮𝗻̃𝗼𝘀")  # Canal de cumpleaños

    if not channel_chat or not channel_cumples:
        print("No se encontraron los canales.")
        return

    celebrants = list(birthdays.find({"date": today}))

    if celebrants:
        for user_data in celebrants:
            user_id = user_data["user_id"]
            await channel_chat.send(f"🎉 ¡Feliz cumpleaños, <@{user_id}>! Que tengas un gran día.")
    
    # Actualizar lista en el canal cumpleaños con formato por mes
    all_birthdays = birthdays.find()
    cumples_por_mes = defaultdict(list)

    for b in all_birthdays:
        try:
            fecha = datetime.strptime(b["date"], "%d-%m")
            mes_nombre = fecha.strftime("%B")
            cumples_por_mes[mes_nombre].append((fecha.day, b["username"]))
        except ValueError:
            continue

    orden_meses = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    message = ""
    for mes in orden_meses:
        if mes in cumples_por_mes:
            message += f"🎈**{mes}**\n"
            for dia, username in sorted(cumples_por_mes[mes]):
                message += f"\t{dia} {username}\n"
            message += "\n"

    pinned = await channel_cumples.pins()
    if pinned:
        await pinned[0].edit(content=message)
    else:
        msg = await channel_cumples.send(message)
        await msg.pin()

# Ejecutar bot
bot.run(DISCORD_TOKEN)
