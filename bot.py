from collections import defaultdict
import datetime
import os
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
intents.guilds = True
intents.voice_states = True
intents.reactions = True
intents.moderation = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Həm Əsas, həm də Tac hesabın ID-ləri
OWNER_IDS = [641014966312501259, 1547667454501724310]
VOICE_CHANNEL_ID = 1507834544756101302
LOG_CHANNEL_ID = 1507883975522128003

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


def clean_text(text):
  text = text.lower()
  replacements = {
      "4": "a",
      "0": "a",
      "3": "e",
      "1": "i",
      "!": "i",
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


# --- CANLI STATİSTİKA STATUS DÖVRÜ ---
@tasks.loop(seconds=10)
async def update_status():
  latency = round(bot.latency * 1000)

  activities = [
      discord.Activity(
          type=discord.ActivityType.watching,
          name="👀 jett sizi izliyor",
      ),
      discord.Activity(
          type=discord.ActivityType.playing,
          name="🛡️ VODKA Security",
      ),
      discord.Activity(
          type=discord.ActivityType.watching, name=f"🏓 Ping: {latency}ms"
      ),
  ]

  for activity in activities:
    await bot.change_presence(activity=activity)
    await asyncio.sleep(10)


# --- BOT HAZIR OLDUQDA ---
@bot.event
async def on_ready():
  print(f"VODKA Bot tam aktivdir: {bot.user}")

  if not update_status.is_running():
    update_status.start()

  if not bot.voice_clients:
    try:
      channel = bot.get_channel(VOICE_CHANNEL_ID)
      if channel and isinstance(channel, discord.VoiceChannel):
        await channel.connect(reconnect=True, self_deaf=True)
    except:
      pass


@bot.event
async def on_voice_state_update(member, before, after):
  if member.id == bot.user.id and after.channel is None:
    try:
      channel = bot.get_channel(VOICE_CHANNEL_ID)
      if channel and isinstance(channel, discord.VoiceChannel):
        await channel.connect(reconnect=True, self_deaf=True)
    except:
      pass


# --- LOG KANALINA MESAJ GÖNDƏRMƏ KÖMƏKÇİSİ ---
async def send_log(guild, embed):
  try:
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
      await log_channel.send(embed=embed)
  except:
    pass


# --- REAKSİYA SİNXRONİZASİYASI ---
@bot.event
async def on_reaction_add(reaction, user):
  if user.bot:
    return
  if user.id in OWNER_IDS:
    try:
      message = reaction.message
      await message.add_reaction(reaction.emoji)
    except:
      pass


@bot.event
async def on_member_join(member):
  try:
    now = discord.utils.utcnow()
    account_age = (now - member.created_at).total_seconds()
    if account_age < 86400 and not member.avatar:
      await member.kick(reason="VODKA Anti-Bot: Şübhəli hesab")
  except:
    pass


@bot.event
async def on_guild_channel_create(channel):
  try:
    async for entry in channel.guild.audit_logs(
        limit=1, action=discord.AuditLogAction.channel_create
    ):
      if entry.user and entry.user.id not in OWNER_IDS and not entry.user.bot:
        member = channel.guild.get_member(entry.user.id)
        if member and member.id not in OWNER_IDS:
          await channel.delete(reason="Sahibdən icazəsiz kanal")
          embed = discord.Embed(
              title="🚨 Təhlükəsizlik Müdaxiləsi",
              description=(
                  f"**İstifadəçi:** {entry.user.mention}\n**Səbəb:** İcazəsiz"
                  " kanal yaratdı və ləğv edildi."
              ),
              color=0xFF0000,
          )
          await send_log(channel.guild, embed)
  except:
    pass


@bot.event
async def on_guild_role_create(role):
  try:
    async for entry in role.guild.audit_logs(
        limit=1, action=discord.AuditLogAction.role_create
    ):
      if entry.user and entry.user.id not in OWNER_IDS and not entry.user.bot:
        member = role.guild.get_member(entry.user.id)
        if member and member.id not in OWNER_IDS:
          await role.delete(reason="Sahibdən icazəsiz rol")
          embed = discord.Embed(
              title="🚨 Təhlükəsizlik Müdaxiləsi",
              description=(
                  f"**İstifadəçi:** {entry.user.mention}\n**Səbəb:** İcazəsiz"
                  " rol yaratdı və silindi."
              ),
              color=0xFF0000,
          )
          await send_log(role.guild, embed)
  except:
    pass


@bot.event
async def on_guild_role_update(before, after):
  try:
    async for entry in after.guild.audit_logs(
        limit=1, action=discord.AuditLogAction.role_update
    ):
      if entry.user and entry.user.id not in OWNER_IDS and not entry.user.bot:
        member = after.guild.get_member(entry.user.id)
        if (
            member
            and member.id not in OWNER_IDS
            and (after.permissions.administrator or after.permissions.manage_guild)
        ):
          await after.edit(
              permissions=before.permissions,
              reason="İcazəsiz səlahiyyət dəyişikliyi bloklandı!",
          )
          embed = discord.Embed(
              title="🛡️ Anti-Nuke Rol Qoruması",
              description=(
                  f"**İstifadəçi:** {entry.user.mention}\n**Rol:**"
                  f" {after.name}\n**Əməliyyat:** Təhlükəli səlahiyyət"
                  " verilməyə çalışıldı və geri alındı."
              ),
              color=0xFFA500,
          )
          await send_log(after.guild, embed)
  except:
    pass


@bot.event
async def on_member_ban(guild, user):
  try:
    async for entry in guild.audit_logs(
        limit=1, action=discord.AuditLogAction.ban
    ):
      actor = entry.user
      if actor and actor.id not in OWNER_IDS and not actor.bot:
        current_time = time.time()
        ban_action_counts[actor.id] = [
            t
            for t in ban_action_counts[actor.id]
            if current_time - t < TIME_WINDOW
        ]
        ban_action_counts[actor.id].append(current_time)

        if len(ban_action_counts[actor.id]) >= LIMIT:
          member = guild.get_member(actor.id)
          if member:
            try:
              await member.ban(reason=f"{guild.name}: Anti-Nuke")
              embed = discord.Embed(
                  title="🚨 Anti-Nuke Ban Kilidi",
                  description=(
                      f"**Kütləvi ban edən şəxs cəzalandırıldı:**"
                      f" {actor.mention}"
                  ),
                  color=0xFF0000,
              )
              await send_log(guild, embed)
            except:
              pass
  except:
    pass


@bot.event
async def on_message_delete(message):
  if message.author.bot or not message.guild:
    return
  if message.author.id in OWNER_IDS:
    return
  embed = discord.Embed(
      title="🗑️ Mesaj Silindi",
      description=(
          f"**Yazar:** {message.author.mention}\n**Kanal:**"
          f" {message.channel.mention}\n**Məzmun:**"
          f" `{message.content or 'Şəkil/Embed'}`"
      ),
      color=0x2B2D31,
  )
  embed.set_footer(text=f"ID: {message.author.id}")
  await send_log(message.guild, embed)


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

  if message.author.id in OWNER_IDS:
    await bot.process_commands(message)
    return

  # Anti-Mass Mention (Kütləvi etiket qoruması)
  if message.mention_everyone or len(message.mentions) > 4:
    try:
      await message.delete()
      until = discord.utils.utcnow() + datetime.timedelta(minutes=5)
      await message.author.timeout(until, reason="Kütləvi etiketləmə")
      warn_msg = await message.channel.send(
          f"{message.author.mention} chatı kirletme oqlm [uyarı 3]"
      )
      await warn_msg.delete(delay=5)
      return
    except:
      pass

  # Anti-Token / Zərərli Link Qoruması
  dangerous_patterns = [
      "discord.gift/",
      "free-nitro",
      "steam-nitro",
      "nitro",
      "discord.com/api/webhooks",
      "grabber",
      "token",
  ]
  if any(pattern in cleaned for pattern in dangerous_patterns):
    try:
      await message.delete()
      until = discord.utils.utcnow() + datetime.timedelta(minutes=5)
      await message.author.timeout(until, reason="Zərərli Link")
      warn_msg = await message.channel.send(
          f"{message.author.mention} chatı kirletme oqlm [uyarı 3]"
      )
      await warn_msg.delete(delay=5)
      return
    except:
      pass

  emoji_count = len(re.findall(r"<a?:\w+:\d+>", content))
  if emoji_count > 6:
    try:
      await message.delete()
      warn_msg = await message.channel.send(
          f"{message.author.mention} chatı kirletme oqlm [uyarı 1]"
      )
      await warn_msg.delete(delay=5)
      return
    except:
      pass

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
          f"{message.author.mention} chatı kirletme oqlm [uyarı 1]"
      )
      await warn_msg.delete(delay=5)
      return
    except:
      pass

  # --- SPAM QORUMASI VƏ 3 UYARI İLƏ 5 DƏQİQƏLİK TIMEOUT ---
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
            f"{message.author.mention} chatı kirletme oqlm [uyarı 1]"
        )
        await warn_msg.delete(delay=5)
      elif count == 2:
        warn_msg = await message.channel.send(
            f"{message.author.mention} chatı kirletme oqlm [uyarı 2]"
        )
        await warn_msg.delete(delay=5)
      elif count >= 3:
        warn_msg = await message.channel.send(
            f"{message.author.mention} chatı kirletme oqlm [uyarı 3]"
        )
        until = discord.utils.utcnow() + datetime.timedelta(minutes=5)
        await message.author.timeout(until, reason="Spam")
        repeat_warnings[author_id] = 0
        await warn_msg.delete(delay=5)
      return
    except:
      pass

  await bot.process_commands(message)


# --- BÜTÜN KOMANDALAR (SAHİBLƏR ÜÇÜN) ---
@bot.command(name="yardim")
async def yardim(ctx):
  if ctx.author.id not in OWNER_IDS:
    return

  embed = discord.Embed(
      title="🛡️ VODKA Təhlükəsizlik və İdarəetmə",
      description="Serverin nizamını qoruyur.",
      color=0x2B2D31,
  )
  embed.add_field(
      name="🎉 Çekiliş", value="!cekilis {dəqiqə} {hədiyyə}", inline=False
  )
  embed.add_field(name="📊 Sorğu", value="!sorğu {sual}", inline=False)
  embed.add_field(name="🔗 Server Url", value="!url", inline=False)
  embed.add_field(
      name="👤 User Məlumatı", value="!userinfo [@istifadəçi]", inline=False
  )
  embed.add_field(
      name="🛡️ Anti-Spam", value="!antispam enable / disable", inline=False
  )
  embed.add_field(name="🔒 Kilid", value="!lock / !unlock / !lockdown", inline=False)
  embed.add_field(name="🧹 Təmizlik", value="!sil {say} | !siluser", inline=False)
  embed.add_field(
      name="⏱️ Digər", value="!slowmode {san} | !ping | !botbilgi", inline=False
  )
  embed.add_field(name="😀 Emojilər", value="!emojinickdeyis {ad}", inline=False)
  embed.set_footer(text=f"{ctx.guild.name} | VODKA Systems")
  await ctx.send(embed=embed)


@bot.command(name="url")
async def server_url(ctx):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    guild = ctx.guild
    invite_link = "discord.gg/VODKA"
    uses_count = "Bilinmir"

    if guild.vanity_url_code:
      try:
        vanity = await guild.vanity_invite()
        invite_link = f"discord.gg/{vanity.code}"
        uses_count = str(vanity.uses)
      except:
        pass

    embed = discord.Embed(
        title=f"👑 {guild.name} — Server Məlumat Mərkəzi",
        description=(
            f"🔗 **Dəvət Linki:**\n👉 **[{invite_link}](https://{invite_link})**"
        ),
        color=0x2B2D31,
    )

    embed.add_field(name="📊 Link İstifadəsi", value=f"`{uses_count}`", inline=True)
    embed.add_field(name="👥 Ümumilikdə Üzv", value=f"`{guild.member_count}`", inline=True)
    embed.add_field(name="👑 Server Sahibi", value=f"{guild.owner.mention}", inline=True)

    if guild.icon:
      embed.set_thumbnail(url=guild.icon.url)

    if guild.banner:
      embed.set_image(url=guild.banner.url)

    embed.set_footer(text=f"{guild.name} | VODKA Systems")
    await ctx.send(embed=embed, delete_after=30)
  except:
    pass


@bot.command(name="userinfo", aliases=["istifadəçi", "whois"])
async def userinfo(ctx, member: discord.Member = None):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    target = member or ctx.author
    roles = [
        role.mention for role in target.roles if role != ctx.guild.default_role
    ]
    roles_str = ", ".join(roles) if roles else "Yoxdur"

    embed = discord.Embed(
        title=f"👤 İstifadəçi Məlumatı — {target.name}", color=0x2B2D31
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="🆔 ID", value=f"`{target.id}`", inline=True)
    embed.add_field(
        name="🏷️ İstifadəçi Adı", value=f"`{target.display_name}`", inline=True
    )
    embed.add_field(
        name="📅 Serverə Qoşulma",
        value=(
            f"`{target.joined_at.strftime('%d.%m.%Y %H:%M')}`"
            if target.joined_at
            else "Bilinmir"
        ),
        inline=False,
    )
    embed.add_field(
        name="🤖 Hesabın Yaradılması",
        value=f"`{target.created_at.strftime('%d.%m.%Y %H:%M')}`",
        inline=False,
    )
    embed.add_field(
        name=f"🎭 Rollar ({len(roles)})", value=roles_str, inline=False
    )
    embed.set_footer(text=f"{ctx.guild.name} | VODKA Systems")
    await ctx.send(embed=embed, delete_after=25)
  except:
    pass


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

    embed = discord.Embed(title="🤖 VODKA Bot Məlumatı", color=0x2B2D31)
    embed.add_field(
        name="⏳ Uptime", value=f"`{hours} saat, {minutes} dəqiqə`", inline=True
    )
    embed.add_field(name="🏓 Ping", value=f"`{latency}ms`", inline=True)
    embed.add_field(
        name="👥 Server Sayı", value=f"`{len(bot.guilds)} server`", inline=True
    )
    embed.set_footer(text=f"{ctx.guild.name} | VODKA")
    await ctx.send(embed=embed, delete_after=15)
  except:
    pass


@bot.command(name="emojinickdeyis")
async def emojinickdeyis(ctx, yeni_ad: str):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    say = 0
    for emoji in ctx.guild.emojis:
      try:
        await emoji.edit(name=yeni_ad)
        say += 1
      except:
        pass
    await ctx.send(
        f"✅ Uğurla **{say}** ədəd emojinin adı **{yeni_ad}** oldu!",
        delete_after=5,
    )
  except:
    pass


@bot.command(name="cekilis")
async def cekilis(ctx, minutes: int, *, prize: str):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    embed = discord.Embed(
        title="🎉 YENİ ÇEKİLİŞ!",
        description=f"Hədiyyə: **{prize}**\nBitmə vaxtı: **{minutes} dəqiqə**",
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
          import random

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

    if new_status:
      await ctx.send("🔓 Fövqəladə vəziyyət ləğv olundu.", delete_after=10)
    else:
      await ctx.send("🚨 Fövqəladə vəziyyət aktivdir!", delete_after=10)
  except:
    pass


@bot.command(name="sil", aliases=["temizle"])
async def sil_komanda(ctx, limit: int = 5):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    deleted = await ctx.channel.purge(limit=limit)
    await ctx.send(f"🧹 {len(deleted)} mesaj təmizləndi.", delete_after=3)
  except:
    pass

@bot.command(name="siluser")
async def siluser(ctx, member: discord.Member, limit: int = 10):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    deleted = await ctx.channel.purge(
        limit=limit, check=lambda m: m.author.id == member.id
    )
    await ctx.send(
        f"🧹 {member.mention} istifadəçisinin {len(deleted)} mesajı"
        " təmizləndi.",
        delete_after=3,
    )
  except:
    pass


@bot.command(name="slowmode", aliases=["yavas"])
async def slowmode(ctx, seconds: int = 0):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await ctx.message.delete()
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(
        f"🐢 Yavaş rejim {seconds} saniyə olaraq tənzimləndi.", delete_after=5
    )
  except:
    pass


@bot.command(name="ping")
async def ping(ctx):
  if ctx.author.id not in OWNER_IDS:
    return
  latency = round(bot.latency * 1000)
  await ctx.send(f"🏓 Gecikmə: **{latency}ms**")


@bot.command(name="serverbilgisi")
async def serverbilgisi(ctx):
  if ctx.author.id not in OWNER_IDS:
    return
  guild = ctx.guild
  embed = discord.Embed(title=f"📊 {guild.name} - Məlumat", color=0x2B2D31)
  embed.add_field(name="👑 Sahib", value=f"{guild.owner}", inline=True)
  embed.add_field(name="👥 Üzv", value=f"{guild.member_count}", inline=True)
  await ctx.send(embed=embed)


@bot.command(name="ban")
async def ban(ctx, member: discord.Member, *, reason="Göstərilməyib"):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await member.ban(reason=reason)
    await ctx.send(f"🔨 {member} banlandı. Səbəb: {reason}")
  except:
    pass


@bot.command(name="kick")
async def kick(ctx, member: discord.Member, *, reason="Göstərilməyib"):
  if ctx.author.id not in OWNER_IDS:
    return
  try:
    await member.kick(reason=reason)
    await ctx.send(f"👢 {member} qovuldu. Səbəb: {reason}")
  except:
    pass


if __name__ == "__main__":
  keep_alive()
  token = os.getenv("DISCORD_TOKEN")
  if token:
    bot.run(token)
  else:
    print("XƏTA: Token tapılmadı!")
    
