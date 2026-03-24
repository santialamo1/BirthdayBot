import discord
from discord.ext import commands
from pymongo import MongoClient
from datetime import datetime, timedelta, timezone, time
import pytz
import os
import random
from collections import defaultdict
import asyncio
from aiohttp import web

# === Servidor web para mantener vivo ===
async def handle_ping(request):
    return web.Response(text="OK")

async def start_webserver():
    app = web.Application()
    app.add_routes([web.get('/ping', handle_ping)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv('PORT', 8080)))
    await site.start()
    print("Servidor web iniciado en /ping")

# === Config ===
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

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["birthdaybot"]
birthdays = db["birthdays"]

argentina_tz = pytz.timezone("America/Argentina/Buenos_Aires")

# ← FIX: una sola definición de update_birthday_message
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
            message += f"\n🎈 **{mes}:**\n"
            for dia, nombre in sorted(organized[mes]):
                message += f"        {dia} - {nombre}\n"

    if not any(mes in organized for mes in months_order):
        message = "No hay cumpleaños registrados aún."

    pinned = await channel_cumples.pins()
    if pinned:
        await pinned[0].edit(content=message)
    else:
        msg = await channel_cumples.send(message)
        await msg.pin()


# === Comandos ===

@bot.command()
async def status(ctx):
    msg = await ctx.send("✅ El bot está activo y funcionando correctamente.")
    await asyncio.sleep(5)
    await msg.delete()
    await ctx.message.delete()


@bot.command()
async def addbirthday(ctx, user_or_name: str = None, name_or_date: str = None, maybe_date: str = None):
    """Admins: !addbirthday @Usuario Nombre DD-MM | Usuarios: !addbirthday Nombre DD-MM"""

    is_admin = ctx.author.guild_permissions.administrator

    if is_admin and ctx.message.mentions:
        user = ctx.message.mentions[0]
        name = name_or_date
        date = maybe_date
    else:
        user = ctx.author
        name = user_or_name
        date = name_or_date

    if ctx.channel.id != CHANNEL_AGGCUMPLE_ID:
        msg = await ctx.reply("❌ Este comando solo se puede usar en el canal de cumpleaños.")
        await asyncio.sleep(30)
        await msg.delete()
        await ctx.message.delete()
        return

    if not name or not date:
        msg = await ctx.reply("❌ Falta información. Formato: `!addbirthday Nombre DD-MM` o `!addbirthday @Usuario Nombre DD-MM` (admins).")
        await asyncio.sleep(30)
        await msg.delete()
        await ctx.message.delete()
        return

    try:
        datetime.strptime(date, "%d-%m")
    except ValueError:
        msg = await ctx.reply("❌ Formato inválido. Usá DD-MM (por ejemplo 23-07).")
        await asyncio.sleep(30)
        await msg.delete()
        await ctx.message.delete()
        return

    if not is_admin and birthdays.find_one({"user_id": user.id}):
        msg = await ctx.reply("❌ Ya registraste tu cumpleaños.")
        await asyncio.sleep(30)
        await msg.delete()
        await ctx.message.delete()
        return

    birthdays.update_one(
        {"user_id": user.id},
        {"$set": {
            "user_id": user.id,
            "username": str(user),
            "name": name,
            "date": date
        }},
        upsert=True
    )

    msg = await ctx.reply(f"✔️ Cumpleaños guardado para **{name}** (<@{user.id}>) el **{date}**.")
    await ctx.message.add_reaction("✅")
    await asyncio.sleep(30)
    await msg.delete()
    await ctx.message.delete()
    await update_birthday_message(ctx)


@bot.command()
async def removebirthday(ctx, user: discord.User = None):
    """Elimina un cumpleaños. Admins pueden eliminar cumpleaños ajenos."""

    is_admin = ctx.author.guild_permissions.administrator
    target = user if user and is_admin else ctx.author

    if user and not is_admin:
        msg = await ctx.reply("❌ Solo los administradores pueden eliminar cumpleaños de otros usuarios.")
        await asyncio.sleep(30)
        await msg.delete()
        await ctx.message.delete()
        return

    if ctx.channel.id != CHANNEL_AGGCUMPLE_ID:
        msg = await ctx.reply("❌ Este comando solo se puede usar en el canal de cumpleaños.")
        await asyncio.sleep(30)
        await msg.delete()
        await ctx.message.delete()
        return

    cumple_info = birthdays.find_one({"user_id": target.id})
    result = birthdays.delete_one({"user_id": target.id})

    if result.deleted_count:
        name = cumple_info.get("name", target.name) if cumple_info else target.name
        msg = await ctx.reply(f"✔️ Cumpleaños de **{name}** (<@{target.id}>) eliminado.")
        await ctx.message.add_reaction("✅")
        await asyncio.sleep(30)
        await msg.delete()
        await ctx.message.delete()
        await update_birthday_message(ctx)
    else:
        msg = await ctx.reply("❌ Ese usuario no tiene cumpleaños registrado.")
        await asyncio.sleep(30)
        await msg.delete()
        await ctx.message.delete()


@bot.command()
@commands.has_permissions(administrator=True)
async def cumpleatrasado(ctx, user: discord.User = None):
    """Solo admins: envía un saludo de cumpleaños atrasado."""

    if ctx.channel.id != CHANNEL_AGGCUMPLE_ID:
        message = await ctx.reply("❌ Este comando solo se puede usar en el canal de cumpleaños.")
        await asyncio.sleep(5)
        await message.delete()
        await ctx.message.delete()
        return

    if not user:
        message = await ctx.reply("❌ Debes mencionar a un usuario. Usa `!cumpleatrasado @usuario`")
        await asyncio.sleep(5)
        await message.delete()
        await ctx.message.delete()
        return

    channel_chat = ctx.guild.get_channel(CHANNEL_CHAT_ID)

    delayed_birthday_messages = [
        "⚔️ ¡El Emperador Jerek extiende sus disculpas! Aunque los tiempos del imperio a veces fallan, hoy saludamos a <@{user_id}> con honor.",
        "👑 ¡Los cronistas del Imperio han cometido un error! Pero el Emperador Jerek no dejará pasar la oportunidad de celebrar el natalicio de <@{user_id}>.",
        "🏰 Aunque el tiempo nos ha jugado una mala pasada, el reino entero celebra hoy el cumpleaños de <@{user_id}> con honor.",
        "🔥 El Emperador Jerek ha decretado que el retraso no debe opacar la celebración. ¡Feliz cumpleaños atrasado, <@{user_id}>!",
        "🌟 Los astros del Imperio se alinean hoy para enmendar el olvido. ¡Saludos, <@{user_id}>, tu día no ha pasado desapercibido!",
        "📜 Se ha enviado un edicto imperial corrigiendo el descuido: ¡<@{user_id}>, el Imperio celebra tu cumpleaños hoy!",
        "🗡️ El Emperador Jerek proclama que <@{user_id}> merece la festividad que el calendario olvidó. ¡Feliz cumpleaños atrasado!",
    ]

    selected_message = random.choice(delayed_birthday_messages).format(user_id=user.id)
    await channel_chat.send(selected_message)
    await asyncio.sleep(5)
    await ctx.message.delete()


# === Lógica de cumpleaños ===

async def check_birthdays():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print("No se encontró el servidor.")
        return

    channel_chat = guild.get_channel(CHANNEL_CHAT_ID)
    if not channel_chat:
        print("No se encontró el canal de chat.")
        return

    today = datetime.now(argentina_tz).strftime("%d-%m")
    celebrants = list(birthdays.find({"date": today}))

    birthday_messages = [
        "👑 En este día especial, el Emperador Jerek se dirige a <@{user_id}> para rendirle homenaje.",
        "🎉 ¡Hoy es un día único en el calendario imperial! El Emperador Jerek extiende sus palabras.",
        "⚔️ En este día glorioso, <@{user_id}> recibe las bendiciones del Emperador Jerek.",
        "🌟 ¡Que el Emperador Jerek proclame este día como el Día de <@{user_id}>!",
        "🧁 ¡<@{user_id}> celebra otro año de vida bajo el reconocimiento y la admiración!",
        "🔥 ¡El Emperador Jerek decreta que el cumpleaños de <@{user_id}> sea celebrado!",
        "🏰 ¡Desde las torres más altas del Imperio, el Emperador Jerek anuncia el natalicio de <@{user_id}>!",
        "🥳 ¡Las campanas resuenan en todo el reino por el cumpleaños de <@{user_id}>!",
        "🗡️ Que los bardos canten y los dragones bailen, pues <@{user_id}> ha nacido en este día glorioso.",
        "👑 El Emperador Jerek eleva su copa por <@{user_id}> y declara festivo en todo el Imperio.",
        "🌌 ¡Los astros se alinean para rendir tributo al nacimiento de <@{user_id}>!",
        "💫 ¡Que el legado de <@{user_id}> crezca tanto como la gloria del Imperio!",
        "📜 Por decreto imperial, el cumpleaños de <@{user_id}> será recordado por generaciones.",
        "🎇 Hoy el firmamento se ilumina con fuegos imperiales en honor a <@{user_id}>.",
        "🏹 Desde las tierras lejanas hasta la capital, todos festejan el natalicio de <@{user_id}>.",
        "🕯️ Que las velas del castillo se enciendan: ¡<@{user_id}> celebra otro año de sabiduría y poder!",
    ]

    if celebrants:
        messages_today = random.sample(birthday_messages, min(len(birthday_messages), len(celebrants)))

        for user_data, message in zip(celebrants, messages_today):
            user_id = user_data["user_id"]
            msg = message.format(user_id=user_id)
            sent_msg = await channel_chat.send(msg)

            # ← FIX: borrar con asyncio.sleep simple en lugar de lógica UTC rota
            async def delete_later(m):
                await asyncio.sleep(86400)  # 24 horas en segundos
                try:
                    await m.delete()
                except discord.NotFound:
                    pass

            asyncio.create_task(delete_later(sent_msg))


# ← FIX: schedule correcto sin localize() sobre datetime ya aware
async def schedule_birthday_check():
    while True:
        now = datetime.now(argentina_tz)
        # Próxima medianoche + 1 minuto en horario argentino
        tomorrow = (now + timedelta(days=1)).date()
        next_run = argentina_tz.localize(datetime.combine(tomorrow, time(hour=0, minute=1)))
        wait_seconds = (next_run - now).total_seconds()
        print(f"[CUMPLES] Próxima revisión en {wait_seconds:.0f}s ({next_run.strftime('%Y-%m-%d %H:%M')} ARG)")
        await asyncio.sleep(wait_seconds)
        await check_birthdays()


# ← FIX: on_ready no llama check_birthdays() directamente para evitar felicitaciones fuera de hora
@bot.event
async def on_ready():
    print(f"¡Bot activo como {bot.user}!")
    asyncio.create_task(schedule_birthday_check())


# === Main ===
async def main():
    await start_webserver()
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
