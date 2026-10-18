from collections import defaultdict
import datetime
import os
import re
import time
from threading import Thread
import discord
from discord.ext import commands
from flask import Flask

# --- FLASK SERVER (7/24 UPTIME) ---
app = Flask(__name__)


@app.route("/")
def home():
  return "Bot 7/24 Aktivdir!"


def run():
  app.run(host="0.0.0.0", port=8080)


def keep_alive():
  t = Thread(target=run)
  t.start()


# --- BOT AYARLARI ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.audit_log = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

OWNER_ID = 641014966312501259
VOICE_CHANNEL_ID = 123456789012345678  # Sənin səs kanalının ID-si

anti_spam_status = {}
user_message_counts = defaultdict(list)
user_last_message = {}
ban_action_counts = defaultdict(list)
kick_action_counts = defaultdict(list)
channel_delete_counts = defaultdict(list)
caps_warnings = defaultdict(int)
long_text_warnings = defaultdict(int)
repeat_warnings = defaultdict(int)

TIME_WINDOW = 15  # Saniyə
LIMIT = 5  # Anti-Nuke limiti: ən azı 5


def clean_text(text):
  text = text.lower()
  replacements = {
      "4": "a",
      "0": "a",
      "3": "e",
      "1": "i",
      "!": "i",
      "0": "o",
      "5": "s",
      "$": "s",
      "7": "t",
      "+": "t",
      "8": "b",
      "9": "g",
  }
  for char, replacement in replacements.items():
    text = text.replace(char, replacement)
  return text.replace(" ", "")


# --- BOT HAZIR OLDUQDA ---
@bot.event
async def on_ready():
  activity = discord.Activity(
      type=discord.ActivityType.watching, name="Zona Təhlükəsizlik Sistemi"
  )
  await bot.change_presence(activity=activity)
  print(f"Zona Təhlükəsizlik Botu tam aktivdir: {bot.user}")

  if not bot.voice_clients:
    try:
      channel = bot.get_channel(VOICE_CHANNEL_ID)
      if channel and isinstance(channel, discord.VoiceChannel):
        await channel.connect(reconnect=True, self_deaf=True)
        print(f"Bot {channel.name} səs kanalına 7/24 daxil oldu!")
    except Exception as e:
      print(f"Səs kanalına qoşularkən xəta: {e}")


# --- SESDEN ÇIXANDA GERİ QOŞULMA ---
@bot.event
async def on_voice_state_update(member, before, after):
  if member.id == bot.user.id and after.channel is None:
    try:
      channel = bot.get_channel(VOICE_CHANNEL_ID)
      if channel and isinstance(channel, discord.VoiceChannel):
        await channel.connect(reconnect=True, self_deaf=True)
    except:
      pass


# --- SAXTA HESAB QORUNMASI ---
@bot.event
async def on_member_join(member):
  try:
    now = discord.utils.utcnow()
    account_age = (now - member.created_at).total_seconds()
    if account_age < 86400 and not member.avatar:
      await member.kick(reason="Zona Anti-Bot: Şübhəli / Yeni yaradılış saxta hesab")
  except:
    pass


# --- WEBHOOK QORUNMASI ---
@bot.event
async def on_webhooks_update(channel):
  try:
    async for entry in channel.guild.audit_logs(
        limit=1, action=discord.AuditLogAction.webhook_create
    ):
      if entry.user and entry.user.id != OWNER_ID and not entry.user.bot:
        member = channel.guild.get_member(entry.user.id)
        if member and not member.guild_permissions.administrator:
          pass
  except:
    pass


# --- KANAL YARADILMASI QORUNMASI ---
@bot.event
async def on_guild_channel_create(channel):
  try:
    async for entry in channel.guild.audit_logs(
        limit=1, action=discord.AuditLogAction.channel_create
    ):
      if entry.user and entry.user.id != OWNER_ID and not entry.user.bot:
        member = channel.guild.get_member(entry.user.id)
        if member and not member.guild_permissions.administrator:
          await channel.delete(reason=f"Administrator və ya Sahibdən icazəsiz kanal")
  except:
    pass


# --- ROL YARADILMASI QORUNMASI ---
@bot.event
async def on_guild_role_create(role):
  try:
    async for entry in role.guild.audit_logs(
        limit=1, action=discord.AuditLogAction.role_create
    ):
      if entry.user and entry.user.id != OWNER_ID and not entry.user.bot:
        member = role.guild.get_member(entry.user.id)
        if member and not member.guild_permissions.administrator:
          await role.delete(reason=f"Administrator və ya Sahibdən icazəsiz rol")
  except:
    pass


# --- ANTİ-NUKE BAN QORUMASI (LİMİT: 5) ---
@bot.event
async def on_member_ban(guild, user):
  try:
    async for entry in guild.audit_logs(
        limit=1, action=discord.AuditLogAction.ban
    ):
      actor = entry.user
      if actor and actor.id != OWNER_ID and not actor.bot:
        current_time = time.time()
        ban_action_counts[actor.id] = [
            t for t in ban_action_counts[actor.id] if current_time - t < TIME_WINDOW
        ]
        ban_action_counts[actor.id].append(current_time)

        if len(ban_action_counts[actor.id]) >= LIMIT:
          member = guild.get_member(actor.id)
          if member:
            try:
              await member.ban(reason=f"{guild.name}: Anti-Nuke: İcazəsiz kütləvi ban")
            except:
              pass
  except:
    pass


# --- MESAJ VƏ TƏHLÜKƏSİZLİK FİLTRLƏRİ ---
@bot.event
async def on_message(message):
  if message.author.bot or not message.guild:
    return

  guild_id = message.guild.id
  if guild_id and not anti_spam_status.get(guild_id, True):
    await bot.process_commands(message)
    return

  content = message.content
  cleaned = clean_text(content)

  if message.author.id == OWNER_ID:
    await bot.process_commands(message)
    return

  # 1. EMOJI SPAM QORUMASI
  emoji_count = len(re.findall(r"<a?:\w+:\d+>", content))
  if emoji_count > 6:
    try:
      await message.delete()
      warn_msg = await message.channel.send(
          f"{message.author.mention}, emoji spam etmək qadağandır!"
      )
      await warn_msg.delete(delay=5)
      return
    except:
      pass

  # 2. ZƏRƏRLİ LİNK QORUMASI
  dangerous_patterns = [
      "discord.gift/",
      "free-nitro",
      "steam-nitro",
      "nitro",
  ]
  if any(pattern in cleaned for pattern in dangerous_patterns):
    try:
      await message.delete()
      until = discord.utils.utcnow() + datetime.timedelta(minutes=1)
      await message.author.timeout(until, reason="Zərərli / Phishing Link")
      warn_msg = await message.channel.send(
          f"{message.author.mention}, şübhəli link paylaşdığı üçün 1 dəqiqə"
          " timeout aldı!"
      )
      await warn_msg.delete(delay=5)
      return
    except:
      pass

  # 3. KÜTLƏVİ ETİKETLƏMƏ QORUMASI
  if message.mention_everyone or len(message.mentions) > 4:
    try:
      await message.delete()
      warn_msg = await message.channel.send(
          f"{message.author.mention}, kütləvi etiketləmə qadağandır!"
      )
      await warn_msg.delete(delay=5)
      return
    except:
      pass

  # 4. REKLAM / LİNK QORUMASI
  link_patterns = [
      "discord.gg/",
      "discord.com/invite",
      "http://",
      "https://",
      "t.me/",
  ]
  if any(domain in content.lower() for domain in link_patterns):
    try:
      await message.delete()
      warn_msg = await message.channel.send(
          f"{message.author.mention}, başqa serverin reklamını etmək qadağandır!"
      )
      await warn_msg.delete(delay=5)
      return
    except:
      pass

  # 5. SƏRT UYARI İLƏ SÜRƏTLİ MESAJ SPAM QORUMASI
  author_id = message.author.id
  current_time = time.time()
  user_message_counts[author_id] = [
      t for t in user_message_counts[author_id] if current_time - t < 5
  ]
  user_message_counts[author_id].append(current_time)

  if len(user_message_counts[author_id]) > 4:
    try:
      await message.delete()
      repeat_warnings[author_id] += 1
      count = repeat_warnings[author_id]

      if count == 1:
        warn_msg = await message.channel.send(
            f"{message.author.mention} Senin doganva soxm yavas yaz [uyarı 1]"
        )
        await warn_msg.delete(delay=5)
      elif count == 2:
        warn_msg = await message.channel.send(
            f"{message.author.mention} Senin doganva soxm yavas yaz [uyarı 2]"
        )
        await warn_msg.delete(delay=5)
      elif count >= 3:
        warn_msg = await message.channel.send(
            f"{message.author.mention} Senin doganva soxm yavas yaz [uyarı 3]"
        )
        until = discord.utils.utcnow() + datetime.timedelta(minutes=5)
        await message.author.timeout(
            until, reason="Spam və xəbərdarlıqlara məhəl qoymamaq"
        )
        repeat_warnings[author_id] = 0
        await warn_msg.delete(delay=5)
      return
    except:
      pass

  await bot.process_commands(message)


# --- BÜTÜN KOMANDALAR ---
@bot.command(name="yardim", aliases=["help"])
async def yardim(ctx):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return

  embed = discord.Embed(
      title="🛡️ Zona Təhlükəsizlik Sistemi",
      description="Serverin nizamını və intizamını qoruyur.",
      color=0x2b2d31,
  )
  embed.add_field(
      name="🔗 Server Url",
      value="!url - Serverin dəvət linkini göstərir.",
      inline=False,
  )
  embed.add_field(
      name="🛡️ Anti-Spam",
      value="!antispam enable / disable - Mühafizəni idarə edir.",
      inline=False,
  )
  embed.add_field(
      name="🔒 Kanal Kilidi",
      value="!lock / !unlock - Kanalı yazışmaya bağlayır/açır.",
      inline=False,
  )
  embed.add_field(
      name="🧹 Ümumi Təmizlik",
      value="!sil {sayı} - Göstərilən sayda mesajı təmizləyir.",
      inline=False,
  )
  embed.add_field(
      name="👤 İstifadəçiyə Özəl Təmizlik",
      value="!siluser {@İstifadəçi} {say} - Müəyyən üzvün mesajlarını təmizləyir.",
      inline=False,
  )
  embed.add_field(
      name="⏱️ Yavaş Rejim / Slowmode",
      value="!slowmode {saniyə} - Kanalı saniyə məhdudiyyəti qoyur.",
      inline=False,
  )
  embed.add_field(
      name="🏓 Ping",
      value="!ping - Botun gecikmə sürətini yoxlayır.",
      inline=False,
  )
  embed.add_field(
      name="📊 Server Bilgisi",
      value="!serverbilgisi - Server haqqında məlumat verir.",
      inline=False,
  )
  embed.set_footer(text=f"{ctx.guild.name} | Zona Security Systems")
  await ctx.send(embed=embed)


@bot.command(name="antispam")
async def antispam(ctx, status: str):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  guild_id = ctx.guild.id
  if status.lower() == "enable":
    anti_spam_status[guild_id] = True
    await ctx.send("✅ Təhlükəsizlik sistemi aktivləşdirildi.")
  elif status.lower() == "disable":
    anti_spam_status[guild_id] = False
    await ctx.send("⚠️ Təhlükəsizlik sistemi söndürüldü.")
  else:
    await ctx.send(
        "❌ İstifadə qaydası: `!antispam enable` və ya `!antispam disable`"
    )


@bot.command(name="lock")
async def lock(ctx):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  try:
    await ctx.message.delete()
    await ctx.channel.set_permissions(
        ctx.guild.default_role, send_messages=False
    )
    await ctx.send(
        f"🔒 Bu kanal ({ctx.channel.name}) təhlükəsizlik protokolu ilə"
        " kilitləndi.",
        delete_after=5,
    )
  except:
    pass


@bot.command(name="unlock")
async def unlock(ctx):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  try:
    await ctx.message.delete()
    await ctx.channel.set_permissions(
        ctx.guild.default_role, send_messages=True
    )
    await ctx.send(
        f"🔓 Kanalın kilidi açıldı, {ctx.channel.name} sakinləri yenidən yaza"
        " bilərsiniz.",
        delete_after=5,
    )
  except:
    pass


@bot.command(name="url")
async def server_url(ctx):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  if ctx.guild.vanity_url_code:
    try:
      vanity = await ctx.guild.vanity_invite()
      await ctx.send(
          f"🔗 **{ctx.guild.name} Dəvət Linki:** `discord.gg/{vanity.code}`"
          f" (**İstifade:** `{vanity.uses}`)"
      )
      return
    except:
      pass
  await ctx.send(f"🔗 **{ctx.guild.name} Dəvət Linki:** `discord.gg/zona`")


@bot.command(name="sil", aliases=["temizle"])
async def sil_komanda(ctx, limit: int = 5):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  try:
    await ctx.message.delete()
    deleted = await ctx.channel.purge(limit=limit)
    await ctx.send(
        f"🧹 **{len(deleted)}** ədəd mesaj təmizləndi.", delete_after=3
    )
  except:
    pass


@bot.command(name="siluser")
async def siluser(ctx, member: discord.Member, limit: int = 10):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  try:
    await ctx.message.delete()
    deleted = await ctx.channel.purge(
        limit=limit, check=lambda m: m.author.id == member.id
    )
    await ctx.send(
        f"🧹 **{member.mention}** istifadəçisinin **{len(deleted)}** ədəd mesajı"
        " təmizləndi.",
        delete_after=3,
    )
  except:
    pass


@bot.command(name="slowmode", aliases=["yavas"])
async def slowmode(ctx, seconds: int = 0):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  try:
    await ctx.message.delete()
    await ctx.channel.edit(slowmode_delay=seconds)
    if seconds == 0:
      await ctx.send(
          "🟢 Bu kanalda yavaş rejim **söndürüldü**.", delete_after=3
      )
    else:
      await ctx.send(
          f"🐢 Bu kanalda yavaş rejim **{seconds} saniyə** olaraq"
          " tənzimləndi.",
          delete_after=5,
      )
  except:
    pass


@bot.command(name="ping")
async def ping(ctx):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  latency = round(bot.latency * 1000)
  await ctx.send(f"🏓 Pong! Botun gecikmə sürəti: **{latency}ms**")


@bot.command(name="serverbilgisi")
async def serverbilgisi(ctx):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  guild = ctx.guild
  embed = discord.Embed(title=f"📊 {guild.name} - Server Məlumatı", color=0x2b2d31)
  embed.add_field(
      name="👑 Server Sahib(e)si", value=f"{guild.owner}", inline=True
  )
  embed.add_field(name="👥 Üzv Sayı", value=f"{guild.member_count}", inline=True)
  embed.add_field(
      name="📅 Yaradılma Tarixi",
      value=guild.created_at.strftime("%d.%m.%Y"),
      inline=True,
  )
  await ctx.send(embed=embed)


@bot.command(name="ban")
async def ban(ctx, member: discord.Member, *, reason="Göstərilməyib"):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  try:
    await member.ban(reason=reason)
    await ctx.send(
        f"🔨 **{member}** serverdən uzaqlaşdırıldı. Səbəb: **{reason}**"
    )
  except:
    pass


@bot.command(name="kick")
async def kick(ctx, member: discord.Member, *, reason="Göstərilməyib"):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  try:
    await member.kick(reason=reason)
    await ctx.send(f"👢 **{member}** serverdən qovuldu. Səbəb: **{reason}**")
  except:
    pass


if __name__ == "__main__":
  keep_alive()
  token = os.getenv("DISCORD_TOKEN")
  if token:
    bot.run(token)
  else:
    print("XƏTA: DISCORD_TOKEN tapılmadı!")
  
