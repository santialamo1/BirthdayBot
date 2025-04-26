import discord
from discord.ext import commands, tasks
from pymongo import MongoClient
from datetime import datetime, timedelta
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
async def addbirthday(ctx, name: str = None, date: str = None, user: discord.User = None):
    """Agrega tu cumpleaños en formato !addbirthday Nombre DD-MM, o !addbirthday Nombre DD-MM @Usuario para admins"""
    user_id = ctx.author.id
    is_admin = ctx.author.guild_permissions.administrator

    # Verificar si el comando fue ejecutado con ambos argumentos
    if not name or not date:
        message = await ctx.reply("❌ Falta información. El formato correcto es: `!addbirthday Nombre DD-MM`")
        await ctx.message.add_reaction("❌")
        return

    # Si no es admin y se menciona otro usuario, no se permite
    if not is_admin and user:
        message = await ctx.reply("❌ No puedes agregar cumpleaños para otros usuarios.")
        await ctx.message.add_reaction("❌")
        return

    # Si el admin menciona a otro usuario, usar el id de ese usuario, sino el del que ejecutó el comando
    target_user = user if is_admin and user else ctx.author

    existing = birthdays.find_one({"user_id": target_user.id})
    if existing:
        message = await ctx.reply("❌ Ese usuario ya registró su cumpleaños.")
        await ctx.message.add_reaction("❌")
        return

    try:
        # Validamos el formato de fecha DD-MM
        datetime.strptime(date, "%d-%m")
    except ValueError:
        message = await ctx.reply("❌ Formato inválido. Usá DD-MM (por ejemplo 23-07).")
        await ctx.message.add_reaction("❌")
        return

    # Insertamos el cumpleaños
    birthdays.insert_one({
        "user_id": target_user.id,
        "username": str(target_user),
        "name": name,
        "date": date
    })

    message = await ctx.reply(f"✔️ Cumpleaños guardado para **{name}** el **{date}**.")
    await ctx.message.add_reaction("✅")  # Éxito

    # Actualizamos la lista de cumpleaños
    await update_birthday_message(ctx)


async def update_birthday_message(ctx):
    guild = ctx.guild
    channel_cumples = guild.get_channel(CHANNEL_CUMPLES_ID)  # Canal para la lista de cumpleaños

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

@bot.command()
@commands.has_permissions(administrator=True)
async def removebirthday(ctx, user: discord.User):
    """Solo admins: elimina un cumpleaños."""
    result = birthdays.delete_one({"user_id": user.id})
    if result.deleted_count:
        await ctx.reply(f"Cumpleaños de {user} eliminado.")
        # Después de eliminar el cumpleaños, actualizamos el mensaje fijado
        await update_birthday_message(ctx)
    else:
        await ctx.reply("Ese usuario no tiene cumpleaños registrado.")

async def update_birthday_message(ctx):
    """Actualiza el mensaje fijado con la lista de cumpleaños."""
    guild = ctx.guild
    channel_cumples = guild.get_channel(CHANNEL_CUMPLES_ID)

    if not channel_cumples:
        print("No se encontró el canal de cumpleaños.")
        return

    # Generar lista organizada por mes (en español)
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

# Reemplaza tu función check_birthdays por esta versión modificada:

@tasks.loop(hours=24)
async def check_birthdays():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print("No se encontró el servidor.")
        return

    channel_chat = guild.get_channel(CHANNEL_CHAT_ID)
    if not channel_chat:
        print("No se encontró el canal de chat.")
        return

    today = datetime.now().strftime("%d-%m")
    celebrants = list(birthdays.find({"date": today}))

    birthday_messages = [
        "👑 En este día especial, el Emperador Jerek se dirige a <@{user_id}> para rendirle homenaje...",
        "🎉 ¡Hoy es un día único en el calendario imperial! El Emperador Jerek extiende sus palabras...",
        "⚔️ En este día glorioso, <@{user_id}> recibe las bendiciones del Emperador Jerek...",
        "🌟 ¡Que el Emperador Jerek proclame este día como el Día de <@{user_id}>!...",
        "🧁 ¡<@{user_id}> celebra otro año de vida bajo el reconocimiento y la admiración...",
        "🔥 ¡El Emperador Jerek decreta que el cumpleaños de <@{user_id}> sea celebrado...",
    ]

    if celebrants:
        for user_data in celebrants:
            user_id = user_data["user_id"]
            msg = random.choice(birthday_messages).format(user_id=user_id)
            sent_msg = await channel_chat.send(msg)

            # ⏳ Eliminar el mensaje después de 24 horas
            async def delete_later(message):
                await discord.utils.sleep_until(datetime.utcnow().replace(hour=message.created_at.hour, minute=message.created_at.minute, second=message.created_at.second) + timedelta(days=1))
                try:
                    await message.delete()
                except discord.NotFound:
                    pass

            bot.loop.create_task(delete_later(sent_msg))


bot.run(DISCORD_TOKEN)
