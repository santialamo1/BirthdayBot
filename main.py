import discord
from discord.ext import commands, tasks
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz  # Se agregó pytz para manejar la zona horaria
import os
import random
from collections import defaultdict
import asyncio

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
CHANNEL_AGGCUMPLE_ID = int(os.getenv("CHANNEL_AGGCUMPLE_ID"))

client = MongoClient(MONGO_URI)
db = client["birthdaybot"]
birthdays = db["birthdays"]

# Zona horaria de Argentina
argentina_tz = pytz.timezone("America/Argentina/Buenos_Aires")

@bot.event
async def on_ready():
    print(f"¡Bot activo como {bot.user}!")
    check_birthdays.start()

@bot.command()
async def addbirthday(ctx, name: str = None, date: str = None):
    """Agrega tu cumpleaños en formato !addbirthday Nombre DD-MM"""
    
    if ctx.channel.id != CHANNEL_AGGCUMPLE_ID:
        message = await ctx.reply("❌ Este comando solo se puede usar en el canal de cumpleaños.")
        await message.add_reaction("❌")
        await asyncio.sleep(30)
        await message.delete()
        await ctx.message.delete()
        return
    
    user_id = ctx.author.id
    is_admin = ctx.author.guild_permissions.administrator

    if not name or not date:
        message = await ctx.reply("❌ Falta información. El formato correcto es: `!addbirthday Nombre DD-MM`")
        await message.add_reaction("❌")
        await asyncio.sleep(30)
        await message.delete()
        await ctx.message.delete()
        return

    if not is_admin:
        existing = birthdays.find_one({"user_id": user_id})
        if existing:
            message = await ctx.reply("❌ Ya registraste tu cumpleaños.")
            await message.add_reaction("❌")
            await asyncio.sleep(30)
            await message.delete()
            await ctx.message.delete()
            return

    try:
        # Validamos el formato de fecha DD-MM
        datetime.strptime(date, "%d-%m")
    except ValueError:
        message = await ctx.reply("❌ Formato inválido. Usá DD-MM (por ejemplo 23-07).")
        await message.add_reaction("❌")
        await asyncio.sleep(30)
        await message.delete()
        await ctx.message.delete()
        return

    birthdays.insert_one({
        "user_id": user_id,
        "username": str(ctx.author),
        "name": name,
        "date": date
    })

    message = await ctx.reply(f"✔️ Cumpleaños guardado para **{name}** el **{date}**.")
    await ctx.message.add_reaction("✅")

    await asyncio.sleep(30)
    await message.delete()
    await ctx.message.delete()

    await update_birthday_message(ctx)

async def update_birthday_message(ctx):
    guild = ctx.guild
    channel_cumples = guild.get_channel(CHANNEL_CUMPLES_ID)

    all_birthdays = birthdays.find()
    organized = defaultdict(list)

    meses_es = {
        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
    }

    for entry in all_birthdays:
        date_str = entry.get("date")
        if not date_str:
            continue

        try:
            dia, mes = date_str.split("-")
            nombre_mes = meses_es.get(mes.zfill(2))
            if nombre_mes:
                organized[nombre_mes].append((int(dia), entry.get("name", entry["username"])))
        except Exception as e:
            print(f"Error procesando cumpleaños: {e}")
            continue

    months_order = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    message = "📅 **Calendario de Cumpleaños 🎂**\n\n🎈 **Cumpleaños por mes** 🎈\n"
    
    for mes in months_order:
        if mes in organized:
            message += f"\n🎈**{mes}:**\n"
            for dia, nombre in sorted(organized[mes]):
                message += f"        {dia} - {nombre}\n"

    if not message.strip():
        message = "No hay cumpleaños registrados aún."

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
    
    if ctx.channel.id != CHANNEL_AGGCUMPLE_ID:
        message = await ctx.reply("❌ Este comando solo se puede usar en el canal de cumpleaños.")
        await message.add_reaction("❌")
        await asyncio.sleep(30)
        await message.delete()
        await ctx.message.delete()
        return

    if not ctx.author.guild_permissions.administrator:
        message = await ctx.reply("❌ No tienes permisos suficientes para usar este comando.")
        await message.add_reaction("❌")
        await asyncio.sleep(30)
        await message.delete()
        await ctx.message.delete()
        return

    result = birthdays.delete_one({"user_id": user.id})

    if result.deleted_count:
        message = await ctx.reply(f"✔️ Cumpleaños de {user} eliminado.")
        await ctx.message.add_reaction("✅")
        await asyncio.sleep(30)
        await message.delete()
        await ctx.message.delete()

        await update_birthday_message(ctx)
    else:
        message = await ctx.reply("❌ Ese usuario no tiene cumpleaños registrado.")
        await message.add_reaction("❌")
        await asyncio.sleep(30)
        await message.delete()
        await ctx.message.delete()

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
        date_str = entry.get("date")  # Usar .get() para evitar errores si no existe la clave
        if not date_str:
            continue  # Si no tiene fecha, ignorar el registro

        try:
            dia, mes = date_str.split("-")
            nombre_mes = meses_es.get(mes.zfill(2))
            if nombre_mes:
                organized[nombre_mes].append((int(dia), entry.get("name", entry["username"])))
        except Exception as e:
            print(f"Error procesando cumpleaños: {e}")
            continue

    # Armar el mensaje de la lista de cumpleaños organizada
    months_order = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    message = "📅 **Calendario de Cumpleaños 🎂**\n\n🎈 **Cumpleaños por mes** 🎈\n"
    
    for mes in months_order:
        if mes in organized:
            message += f"\n🎉 **{mes}:**\n"  # Título de cada mes con un emoji
            for dia, nombre in sorted(organized[mes]):
                message += f"        {dia} - {nombre}\n"  # Detalle de cada cumpleaños

    if not message.strip():
        message = "No hay cumpleaños registrados aún."

    # 📌 Actualizar o fijar el mensaje en el canal de cumpleaños
    pinned = await channel_cumples.pins()
    if pinned:
        await pinned[0].edit(content=message)
    else:
        msg = await channel_cumples.send(message)
        await msg.pin()

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
