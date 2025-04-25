import discord
from discord.ext import commands, tasks
from pymongo import MongoClient
from datetime import datetime
import os
import random
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
async def addbirthday(ctx, name: str, date: str):
    """Agrega tu cumpleaños en formato !addbirthday Nombre DD-MM"""
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
        "name": name,
        "date": date
    })

    await ctx.reply(f"Cumpleaños guardado para {name} el {date}.")

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

    channel_chat = guild.get_channel(CHANNEL_CHAT_ID)  # Enviar al canal de chat para saludos
    channel_cumples = guild.get_channel(CHANNEL_CUMPLES_ID)  # Canal para la lista de cumpleaños

    if not channel_chat or not channel_cumples:
        print("No se encontraron los canales.")
        return

    today = datetime.now().strftime("%d-%m")
    celebrants = list(birthdays.find({"date": today}))

    # Generar mensaje de cumpleaños
    birthday_messages = [
    "👑 En este día especial, el Emperador Jerek se dirige a <@{user_id}> para rendirle homenaje. ¡Tu lealtad y valentía han sido pilares de nuestra grandeza! Que este cumpleaños te traiga prosperidad, éxitos y alegría sin igual. El Imperio entero celebra contigo. 🎂",
    "🎉 ¡Hoy es un día único en el calendario imperial! El Emperador Jerek extiende sus palabras de sabiduría y gratitud a <@{user_id}>. Tu compromiso con el Imperio es digno de canciones y crónicas. Que los festejos sean abundantes y tus deseos se hagan realidad. 🥳",
    "⚔️ En este día glorioso, <@{user_id}> recibe las bendiciones del Emperador Jerek. Tu dedicación fortalece nuestras tierras y eleva nuestra causa. Que tu cumpleaños esté lleno de momentos memorables y triunfos dignos de tu grandeza. 🎈",
    "🌟 ¡Que el Emperador Jerek proclame este día como el Día de <@{user_id}>! Tus esfuerzos y devoción son inspiración para todos los habitantes del Imperio. Que los festejos estén llenos de luz, alegría y momentos dignos de recordar. 🎁",
    "🧁 ¡<@{user_id}> celebra otro año de vida bajo el reconocimiento y la admiración del Emperador Jerek! Este día está marcado por el honor y la celebración que mereces. Que tu futuro esté lleno de gloria y felicidad. 🍷",
    "🔥 ¡El Emperador Jerek decreta que el cumpleaños de <@{user_id}> sea celebrado con festivales y júbilo en todo el Imperio! Tus contribuciones a nuestra comunidad son eternas, y tu grandeza no pasa desapercibida. ¡Felicidades en este día especial! 🌟",
]


    if celebrants:
        for user_data in celebrants:
            user_id = user_data["user_id"]
            msg = random.choice(birthday_messages).format(user_id=user_id)  # Elige aleatoriamente un mensaje
            await channel_chat.send(msg)  # Enviar el mensaje al canal de chat

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
                organized[nombre_mes].append((int(dia), entry.get("name", entry["username"])))
        except:
            continue

    # Armar el mensaje de la lista de cumpleaños organizada
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

    # 📌 Actualizar o fijar el mensaje en el canal de cumpleaños
    pinned = await channel_cumples.pins()
    if pinned:
        await pinned[0].edit(content=message)
    else:
        msg = await channel_cumples.send(message)
        await msg.pin()

bot.run(DISCORD_TOKEN)
