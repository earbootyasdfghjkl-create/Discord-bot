from collections import defaultdict
import datetime
import os
import random
import re
import time
from threading import Thread
import asyncio
import discord
from discord.ext import commands, tasks
from flask import Flask

# --- FLASK SERVER (7/24 UPTIME) ---
app = Flask(__name__)


@app.route("/")
def home():
  return "VODKA Bot 7/24 Aktivdir!"


def run():
  app.run(host="0.0.0.0", port=8080)


def keep_alive():
  t = Thread(target=run)
  t.start()


# --- BOT AYARLARI ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True
intents.reactions = True
intents.moderation = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Bot Owner, həm də taç hesabın ID-ləri
OWNER_IDS = [641014966312501259, 1547667454501724310]
VOICE_CHANNEL_ID = 1507834344756101302
LOG_CHANNEL_ID = 1507830975522120003

# Sniper Kanalları
URL_SNIPER_CHANNEL_ID = 1565484744022560831
NICK_SNIPER_CHANNEL_ID = 1565484778453737532

start_time = time.time()

anti_spam_status = {}
user_message_counts = defaultdict(list)
user_last_message = {}
ban_action_counts = defaultdict(list)
kick_action_counts = defaultdict(list)
channel_delete_counts = defaultdict(list)
repeat_warnings = defaultdict(int)

TIME_WINDOW = 15
LIMIT = 5

# --- GÜNLÜK HORTORFLI LOGLAMA VƏ YADDAŞ ---
daily_logs = []


async def add_daily_log(guild, text):
  timestamp = datetime.datetime.now().strftime("%H:%M:%S")
  log_entry = f"[{timestamp}] {text}"
  daily_logs.append(log_entry)
  try:
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
      await log_channel.send(f"```{log_entry}```")
  except:
    pass


def clear_text(text):
  text = text.lower()
  replacements = {
      "İ": "i",
      "I": "ı",
      "Ş": "ş",
      "Ğ": "ğ",
      "Ü": "ü",
      "Ö": "ö",
      "Ç": "ç",
      "Ə": "ə",
  }
  for k, v in replacements.items():
    text = text.replace(k, v)
  return text


# --- BÖLGƏLƏR VƏ QADAĞAN OLUNMUŞ SÖZLƏR ---
restricted_words = [
    "cavid",
    "cavidan",
    "cavidka",
    "cavidm",
    "cavidmm",
    "cavidmmd",
    "cavidmammadov",
    "cavidmmdov",
    "cavidmammadov-cell",
    "cavidmmdov-cell",
    "cavidmamedov",
    "cavidmamedov-cell",
    "cavidmammadovcell",
    "cavidmmdovcell",
    "cavidmamedovcell",
    "ceylun",
    "ceylunm",
    "ceylunmm",
    "ceylunmmd",
    "ceylunmammadov",
    "ceylunmmdov",
    "ceylunmammadov-cell",
    "ceylunmmdov-cell",
    "ceylunmamedov",
    "ceylunmamedov-cell",
    "ceylunmammadovcell",
    "ceylunmmdovcell",
    "ceylunmamedovcell",
    "cavidanmmd",
    "cavidanmammadov",
    "cavidanmmdov",
    "cavidanmammadov-cell",
    "cavidanmmdov-cell",
    "cavidanmamedov",
    "cavidanmamedov-cell",
    "cavidanmammadovcell",
    "cavidanmmdovcell",
    "cavidanmamedovcell",
    "cavidanm",
    "cavidanmm",
    "cavidanməmmədov",
    "cavidməmmədov",
    "ceylunməmmədov",
    "cavidanməmmədov-cell",
    "cavidməmmədov-cell",
    "ceylunməmmədov-cell",
    "cavidanməmmədovcell",
    "cavidməmmədovcell",
    "ceylunməmmədovcell",
    "cavidanmammadov-sel",
    "cavidmammadov-sel",
    "ceylunmammadov-sel",
    "cavidanmmdov-sel",
    "cavidmmdov-sel",
    "ceylunmmdov-sel",
    "cavidanmamedov-sel",
    "cavidmamedov-sel",
    "ceylunmamedov-sel",
    "cavidanmammadovsel",
    "cavidmammadovsel",
    "ceylunmammadovsel",
    "cavidanmmdovsel",
    "cavidmmdovsel",
    "ceylunmmdovsel",
    "cavidanmamedovsel",
    "cavidmamedovsel",
    "ceylunmamedovsel",
    "cavidanməmmədov-sel",
    "cavidməmmədov-sel",
    "ceylunməmmədov-sel",
    "cavidanməmmədovsel",
    "cavidməmmədovsel",
    "ceylunməmmədovsel",
    "cavidanmamedovs",
    "cavidmamedovs",
    "ceylunmamedovs",
    "cavidanmammadovs",
    "cavidmammadovs",
    "ceylunmammadovs",
    "cavidanməmmədovs",
    "cavidməmmədovs",
    "ceylunməmmədovs",
    "cavidanmmds",
    "cavidmmds",
    "ceylunmmds",
    "cavidans",
    "cavidms",
    "ceyluns",
    "cavidan-cell",
    "cavidan-sel",
    "cavidansel",
    "cavidanmammadovun",
    "cavidmammadovun",
    "cavidmmdovun",
    "cavidanməmmədovun",
    "cavidməmmədovun",
    "cavidanmammadovunur",
    "cavidmammadovunur",
    "cavidmmdovunur",
    "cavidanməmmədovunur",
    "cavidməmmədovunur",
    "cavidanmammadovunundur",
    "cavidmammadovunundur",
    "cavidmmdovunundur",
    "cavidanməmmədovunundur",
    "cavidməmmədovunundur",
    "cavidanmammadovuncadir",
    "cavidmammadovuncadir",
    "cavidmmdovuncadir",
    "cavidanməmmədovuncadir",
    "cavidməmmədovuncadir",
    "cavidanmammadovuncadirdi",
    "cavidmammadovuncadirdi",
    "cavidmmdovuncadirdi",
    "cavidanməmmədovuncadirdi",
    "cavidməmmədovuncadirdi",
    "cavidanmammadovdur",
    "cavidmammadovdur",
    "cavidmmdovdur",
    "cavidanməmmədovdur",
    "cavidməmmədovdur",
    "cavidanmammadovdurdur",
    "cavidmammadovdurdur",
    "cavidmmdovdurdur",
    "cavidanməmmədovdurdur",
    "cavidməmmədovdurdur",
    "cavidanmammadovdurdurki",
    "cavidmammadovdurdurki",
    "cavidmmdovdurdurki",
    "cavidanməmmədovdurdurki",
    "cavidməmmədovdurdurki",
    "cavidanmammadovunurki",
    "cavidmammadovunurki",
    "cavidmmdovunurki",
    "cavidanməmmədovunurki",
    "cavidməmmədovunurki",
    "cavidanmammadovunundurkide",
    "cavidmammadovunundurkide",
    "cavidmmdovunundurkide",
    "cavidanməmmədovunundurkide",
    "cavidməmmədovunundurkide",
    "cavidanmammadovunundurkideş",
    "cavidmammadovunundurkideş",
    "cavidmmdovunundurkideş",
    "cavidanməmmədovunundurkideş",
    "cavidməmmədovunundurkideş",
    "cavidanmammadovunundurkideşki",
    "cavidmammadovunundurkideşki",
    "cavidmmdovunundurkideşki",
    "cavidanməmmədovunundurkideşki",
    "cavidməmmədovunundurkideşki",
    "cavidanmammadovunundurkideşkidur",
    "cavidmammadovunundurkideşkidur",
    "cavidmmdovunundurkideşkidur",
    "cavidanməmmədovunundurkideşkidur",
    "cavidməmmədovunundurkideşkidur",
    "cavidanmammadovunundurkideşkidurdur",
    "cavidmammadovunundurkideşkidurdur",
    "cavidmmdovunundurkideşkidurdur",
    "cavidanməmmədovunundurkideşkidurdur",
    "cavidməmmədovunundurkideşkidurdur",
    "cavidanmammadovunundurkideşkidurdurki",
    "cavidmammadovunundurkideşkidurdurki",
    "cavidmmdovunundurkideşkidurdurki",
    "cavidanməmmədovunundurkideşkidurdurki",
    "cavidməmmədovunundurkideşkidurdurki",
]

censored_words = [
    "sik",
    "sikiş",
    "amcik",
    "amcık",
    "qəhbə",
    "gehbə",
    "sürtük",
    "surtuk",
    "gijdlaq",
    "gijdılq",
    "peysər",
    "peyser",
    "manyak",
    "axmaq",
    "yarrak",
    "yarak",
    "pidor",
    "pıdor",
    "göt",
    "got",
    "götverən",
    "gotveren",
    "orospu",
    "orosbu",
    "anasını",
    "bacını",
    "cınqıl",
    "cindir",
    "cibiş",
    "dözer",
    "doxan",
    "eşşək",
    "it oğlu",
    "itogluhan",
    "kələkbaz",
    "kərtənkələ",
    "mal",
    "murdar",
    "nanay",
    "paxıl",
    "qotur",
    "sarsağ",
    "tutuquşu",
    "vaybed",
    "zəhləm",
]


# --- BOT HAZIR OLAN KİMİ ---
@bot.event
async def on_ready():
  print(f"{bot.user.name} 7/24 Aktivdir!")
  bot.loop.create_task(update_status())
  bot.loop.create_task(url_sniper_task())
  bot.loop.create_task(nick_sniper_task())

  try:
    channel = bot.get_channel(VOICE_CHANNEL_ID)
    if channel:
      await channel.connect()
      print("Səs kanalına qoşuldu!")
  except Exception as e:
    print(f"Səs kanalına qoşulma xətası: {e}")


# --- STATU DƏYİŞDİRƏN (LOOP) ---
async def update_status():
  activities = [
      discord.Activity(
          type=discord.ActivityType.watching, name="👀 Jett sizi izləyir"
      ),
      discord.Activity(
          type=discord.ActivityType.playing, name="🛡️ VODKA Security"
      ),
      discord.Activity(
          type=discord.ActivityType.playing,
          name=f"🏓 Ping: {round(bot.latency*1000)}ms",
      ),
  ]
  while True:
    for activity in activities:
      try:
        await bot.change_presence(activity=activity)
      except:
        pass
      await asyncio.sleep(10)


# --- URL & NICK SNIPER (KANALLARDA CANLI GÖSTƏRƏN) ---
@tasks.loop(seconds=5.0)
async def url_sniper_task():
  try:
    channel = bot.get_channel(URL_SNIPER_CHANNEL_ID)
    if channel:
      guild = channel.guild
      # URL yoxlanılır statusu
      await add_daily_log(
          guild, "[URL Sniper] Canlı yoxlama aparıldı: Hələlik dəyişiklik yoxdur."
      )
  except:
    pass


@tasks.loop(seconds=5.0)
async def nick_sniper_task():
  try:
    channel = bot.get_channel(NICK_SNIPER_CHANNEL_ID)
    if channel:
      guild = channel.guild
      # Nick yoxlanılır statusu
      await add_daily_log(
          guild, "[Nick Sniper] Canlı yoxlama aparıldı: Hələlik dəyişiklik yoxdur."
      )
  except:
    pass


# --- AVTOMATİK TƏHLÜKƏSİZLİK VƏ ANTİSPAM ---
@bot.event
async def on_message(message):
  if message.author.bot:
    return

  guild_id = message.guild.id
  if anti_spam_status.get(guild_id, False):
    now = time.time()
    author_id = message.author.id

    user_message_counts[author_id] = [
        t for t in user_message_counts[author_id] if now - t < TIME_WINDOW
    ]
    user_message_counts[author_id].append(now)

    if len(user_message_counts[author_id]) > LIMIT:
      try:
        await message.delete()
        warning_msg = await message.channel.send(
            f"⚠️ {message.author.mention}, spam etmə! Dayan."
        )
        await warning_msg.delete(delay=5)
        return
      except:
        pass

  # Küfr və senzura yoxlaması
  cleaned_content = clear_text(message.content)
  for word in censored_words:
    if word in cleaned_content:
      try:
        await message.delete()
        await add_daily_log(
            message.guild,
            f"Senzura: {message.author} küfr işlətdiyi üçün mesajı silindi.",
        )
        warn = await message.channel.send(
            f"❌ {message.author.mention}, bu sözü işlətmək qadağandır!"
        )
        await warn.delete(delay=4)
        return
      except:
        pass

  # Qadağan olunmuş adlar / ifadələr
  for word in restricted_words:
    if word in cleaned_content:
      try:
        await message.delete()
        await message.author.ban(reason="Qadağan olunmuş ifadə/ad.")
        await add_daily_log(
            message.guild,
            f"BAN: {message.author} qadağan olunmuş ifadəyə görə banlandı.",
        )
        return
      except:
        pass

  await bot.process_commands(message)


# --- 11. BEYİN KİMİ İŞLƏYƏN !YARDIM KOMANDASI ---
@bot.command(name="yardım", aliases=["yardim", "help"])
async def yardim(ctx):
  try:
    await ctx.message.delete()
    embed = discord.Embed(
        title="🤖 VODKA Security - Bot Əmrləri",
        description=(
            "Salam! Aşağıda bütün qoruma, moderatorluq və idarəetmə"
            " əmrləri siyahısı göstərilmişdir:"
        ),
        color=0x2B2D31,
    )

    embed.add_field(
        name="🛡️ Təhlükəsizlik və Antispam",
        value=(
            "`!antispam enable/disable` - Server qoruma sistemini"
            " açır/bağlayır\n`!lock` - Cari kanalı kilidləyir\n`!unlock` -"
            " Kanalın kilidini açır\n`!lockdown` - Bütün kanalları"
            " kilidləyir/açır"
        ),
        inline=False,
    )

    embed.add_field(
        name="🧹 Təmizlik Əmrləri",
        value=(
            "`!sil [say]` - Göstərilən sayda mesajı silir (Defolt: 10)\n`!siluser"
            " [@user] [say]` - Müəyyən istifadəçinin mesajlarını silir"
        ),
        inline=False,
    )

    embed.add_field(
        name="⚙️ İdarəetmə və Əyləncə",
        value=(
            "`!slowmode [saniyə]` - Kanala slowmode qoyur\n`!ping` - Botun"
            " gecikmə sürətini göstərir\n`!çekiliş [dəqiqə] [hədiyyə]` -"
            " Çekiliş başladır\n`!sorğu [sual]` - Səsvermə yaradır"
        ),
        inline=False,
    )

    embed.set_footer(
        text=f"Sorğulayan: {ctx.author.name} | VODKA Systems",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else None,
    )
    await ctx.send(embed=embed, delete_after=35)
  except:
    pass


# --- DİGƏR ƏMRLƏR ---
@bot.command(name="botbilgi")
async def botbilgi(ctx):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    uptime_seconds = int(time.time() - start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    latency = round(bot.latency * 1000)

    embed = discord.Embed(title="📊 VODKA Bot Məlumatı", color=0x2B2D31)
    embed.add_field(
        name="⏳ Uptime", value=f"{hours} saat, {minutes} dəqiqə", inline=True
    )
    embed.add_field(name="🏓 Ping", value=f"{latency}ms", inline=True)
    embed.add_field(
        name="🌐 Server Sayı", value=f"{len(bot.guilds)} server", inline=True
    )
    embed.set_footer(text=f"{ctx.guild.name} | VODKA")
    await ctx.send(embed=embed, delete_after=15)
  except:
    pass


@bot.command(name="emojinickdeyis")
async def emojinickdeyis(ctx, yenni_ad: str):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    say = 0
    for emoji in ctx.guild.emojis:
      try:
        await emoji.edit(name=yenni_ad)
        say += 1
      except:
        pass
    await ctx.send(
        f"✅ Ugurla `{say}` eded emojinin adi `{yenni_ad}` olut.",
        delete_after=5,
    )
  except:
    pass


@bot.command(name="çekiliş")
async def cekilis(ctx, minutes: int, *, prize: str):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    embed = discord.Embed(
        title="🎉 YENİ ÇEKİLİŞ! 🎉",
        description=f"Hədiyyə: **{prize}**\nBitmə vaxtı: **{minutes}** dəqiqə.",
        color=0xFFD700,
    )
    embed.set_footer(text="VODKA Systems")

    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")

    await asyncio.sleep(minutes * 60)

    new_msg = await ctx.channel.fetch_message(msg.id)
    winner = None
    for reaction in new_msg.reactions:
      if str(reaction.emoji) == "🎉":
        users = [user async for user in reaction.users() if not user.bot]
        if users:
          winner = random.choice(users)

    if winner:
      await ctx.send(
          f"🏆 Qalib: {winner.mention}! Qazandığın hədiyyə: **{prize}** 🎉"
      )
    else:
      await ctx.send("❌ Qalib seçilmədi.")
  except:
    pass


@bot.command(name="sorğu", aliases=["sorqu", "poll"])
async def sorqu(ctx, *, question: str):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    embed = discord.Embed(
        title="📊 Səsvermə", description=f"**Sual:** {question}", color=0x00AE86
    )
    embed.set_footer(text="VODKA Systems")

    msg = await ctx.send(embed=embed)
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")
  except:
    pass


@bot.command(name="antispam")
async def antispam(ctx, status: str):
  if ctx.author.id not in OWNER_IDS:
    return
  guild_id = ctx.guild.id
  if status.lower() == "enable":
    anti_spam_status[guild_id] = True
    await ctx.send("✅ Təhlükəsizlik sistemi aktivləşdirildi.")
  elif status.lower() == "disable":
    anti_spam_status[guild_id] = False
    await ctx.send("⚠️ Təhlükəsizlik sistemi söndürüldü.")
  else:
    await ctx.send("❌ `!antispam enable` / `!antispam disable`")


@bot.command(name="lock")
async def lock(ctx):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    await ctx.channel.set_permissions(
        ctx.guild.default_role, send_messages=False
    )
    await ctx.send("🔒 Kanal kilitləndi.", delete_after=5)
  except:
    pass


@bot.command(name="unlock")
async def unlock(ctx):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    await ctx.channel.set_permissions(
        ctx.guild.default_role, send_messages=True
    )
    await ctx.send("🔓 Kanalın kilidi açıldı.", delete_after=5)
  except:
    pass


@bot.command(name="lockdown")
async def lockdown(ctx):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    guild = ctx.guild
    current_perms = guild.default_role.permissions.send_messages
    new_status = not current_perms
    for channel in guild.text_channels:
      await channel.set_permissions(
          guild.default_role, send_messages=new_status
      )
    status_text = "kilitləndi" if not new_status else "açıldı"
    await ctx.send(
        f"🚨 Bütün kanallar uğurla **{status_text}**!", delete_after=5
    )
  except:
    pass


@bot.command(name="sil")
async def sil(ctx, amount: int = 10):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    deleted = await ctx.channel.purge(limit=amount)
    msg = await ctx.send(f"🧹 `{len(deleted)}` mesaj silindi.")
    await msg.delete(delay=3)
  except:
    pass


@bot.command(name="siluser")
async def siluser(ctx, member: discord.Member, amount: int = 20):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()

    def check(m):
      return m.author == member

    deleted = await ctx.channel.purge(limit=amount, check=check)
    msg = await ctx.send(
        f"🧹 {member.mention} istifadəçisinin `{len(deleted)}` mesajı silindi."
    )
    await msg.delete(delay=3)
  except:
    pass


@bot.command(name="slowmode")
async def slowmode(ctx, seconds: int = 0):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    await ctx.channel.edit(slowmode_delay=seconds)
    msg = await ctx.send(f"⏱️ Slowmode `{seconds}` saniyə olaraq ayarlandı.")
    await msg.delete(delay=3)
  except:
    pass


@bot.command(name="ping")
async def ping(ctx):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    latency = round(bot.latency * 1000)
    msg = await ctx.send(f"🏓 Pong! `{latency}ms`")
    await msg.delete(delay=5)
  except:
    pass


# --- BOTU İŞƏ SAL ---
keep_alive()
TOKEN = os.environ.get("TOKEN")
if TOKEN:
  bot.run(TOKEN)
