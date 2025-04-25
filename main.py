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

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
GUILD_ID = int(os.getenv("GUILD_ID"))
CHANNEL_CHAT_ID = int(os.getenv("CHANNEL_CHAT_ID"))
CHANNEL_CUMPLES_ID = int(os.getenv("CHANNEL_CUMPLES_ID"))

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

    birthdays.update_one(
        {"user_id": user_id},
        {"$set": {"username": str(ctx.author), "date": date}},
        upsert=True
    )

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
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print("No se encontró el servidor.")
        return

    channel_chat = guild.get_channel(CHANNEL_CHAT_ID)
    channel_cumples = guild.get_channel(CHANNEL_CUMPLES_ID)

    if not channel_chat or not channel_cumples:
        print("No se encontraron los canales.")
        return

    today = datetime.now().strftime("%d-%m")
    celebrants = list(birthdays.find({"date": today}))

    if celebrants:
        for user_data in celebrants:
            user_id = user_data["user_id"]
            await channel_chat.send(f"🎉 ¡Feliz cumpleaños, <@{user_id}>! Que tengas un gran día.")

    # 🎂 Generar lista organizada por mes (en español)
    all_birthdays = birthdays.find()
    organized = defaultdict(list)
    
    meses_es = {
        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
    }

    for entry in all_birthdays:
        date_str = entry["date"]
        try:
            dia, mes = date_str.split("-")
            nombre_mes = meses_es.get(mes.zfill(2))
            if nombre_mes:
                organized[nombre_mes].append((int(dia), entry["username"]))
        except:
            continue

    # Armar el mensaje
    months_order = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    message = ""
    for mes in months_order:
        if mes in organized:
            message += f"\n🎈{mes}\n"
            for dia, nombre in sorted(organized[mes]):
                message += f"        {dia} {nombre}\n"

    if not message.strip():
        message = "No hay cumpleaños registrados aún."

    # 📌 Actualizar o fijar mensaje
    pinned = await channel_cumples.pins()
    if pinned:
        await pinned[0].edit(content=message)
    else:
        msg = await channel_cumples.send(message)
        await msg.pin()


bot.run(DISCORD_TOKEN)
