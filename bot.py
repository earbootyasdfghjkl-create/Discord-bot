
from collections import defaultdict
import datetime
import os
import re
import time
from threading import Thread
import asyncio
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
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
TARGET_PANEL_CHANNEL_ID = 1561265942795649024  # Şikayət kanalının ID-si

anti_spam_status = {}
user_message_counts = defaultdict(list)
user_last_message = {}
ban_action_counts = defaultdict(list)
kick_action_counts = defaultdict(list)
channel_delete_counts = defaultdict(list)
repeat_warnings = defaultdict(int)

# Biletlər üçün sıra nömrəsi sayğacı (yaddaşda saxlanılır)
ticket_counter = 0

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
  total_members = sum(guild.member_count for guild in bot.guilds)
  latency = round(bot.latency * 1000)

  activities = [
      discord.Activity(
          type=discord.ActivityType.watching,
          name=f"👥 {total_members} Üzvü qoruyur",
      ),
      discord.Activity(
          type=discord.ActivityType.playing,
          name="🛡️ Zona Security Systems",
      ),
      discord.Activity(
          type=discord.ActivityType.watching, name=f"🏓 Ping: {latency}ms"
      ),
  ]

  for activity in activities:
    await bot.change_presence(activity=activity)
    await asyncio.sleep(10)


# --- TICKET (ŞİKAYƏT) DÜYMƏ PANELİ VIEW ---
class TicketButtonView(View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="Şikayət / Dəstək Aç 📩",
      style=discord.ButtonStyle.blurple,
      custom_id="open_ticket_button",
  )
  async def open_ticket(
      self, interaction: discord.Interaction, button: discord.Button
  ):
    global ticket_counter
    ticket_counter += 1
    ticket_name = f"ticket-{ticket_counter:03d}"  # Məsələn: ticket-001, ticket-002

    guild = interaction.guild
    member = interaction.user

    # İcazələr: Yalnız Owner (və ya adminlər) və bileti açan şəxs görə bilər
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
        ),
        guild.get_member(OWNER_ID): discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
        ),
    }

    try:
      channel = await guild.create_text_channel(
          name=ticket_name,
          overwrites=overwrites,
          reason=f"Şikayət bileti açıldı: {member}",
      )

      close_view = TicketCloseView()

      embed = discord.Embed(
          title=f"🎫 Şikayət / Dəstək Mərkəzi | {ticket_name}",
          description=(
              f"Salam {member.mention},\nBiletiniz uğurla açıldı! Şikayətinizi"
              " və ya probleminizi ətraflı şəkildə buraya yazın.\n\nYalnız"
              " sizə xüsusi olaraq bu kanal açıldı."
          ),
          color=0x2b2d31,
      )
      embed.set_footer(text=f"Zona Security Systems | Bilet No: {ticket_name}")

      await channel.send(
          content=f"{member.mention} <@!{OWNER_ID}>",
          embed=embed,
          view=close_view,
      )
      await interaction.response.send_message(
          f"✅ Şikayət kanalınız yaradıldı: {channel.mention}", ephemeral=True
      )
    except Exception as e:
      await interaction.response.send_message(
          "❌ Bilet açılarkən xəta baş verdi!", ephemeral=True
      )


# Biletləri bağlamaq üçün düymə
class TicketCloseView(View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="Bileti Bağla 🔒",
      style=discord.ButtonStyle.danger,
      custom_id="close_ticket_button",
  )
  async def close_ticket(
      self, interaction: discord.Interaction, button: discord.Button
  ):
    await interaction.response.send_message(
        "🔒 Bu bilet 5 saniyə ərzində silinəcək...", ephemeral=False
    )
    await asyncio.sleep(5)
    try:
      await interaction.channel.delete(reason="Şikayət bilet bağlandı")
    except:
      pass


# --- BOT HAZIR OLDUQDA ---
@bot.event
async def on_ready():
  print(f"Zona Təhlükəsizlik Botu tam aktivdir: {bot.user}")
  bot.add_view(TicketButtonView())  # Düymələrin yaddaşda qalması üçün

  if not update_status.is_running():
    update_status.start()

  if not bot.voice_clients:
    try:
      channel = bot.get_channel(VOICE_CHANNEL_ID)
      if channel and isinstance(channel, discord.VoiceChannel):
        await channel.connect(reconnect=True, self_deaf=True)
        print(f"Bot {channel.name} səs kanalına 7/24 daxil oldu!")
    except Exception as e:
      print(f"Səs kanalına qoşularkən xəta: {e}")


# --- SƏSDƏN ÇIXANDA GERİ QOŞULMA ---
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
      await member.kick(
          reason="Zona Anti-Bot: Şübhəli / Yeni yaradılış saxta hesab"
      )
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
          await channel.delete(
              reason="Administrator və ya Sahibdən icazəsiz kanal"
          )
  except:
    pass


# --- ROL YARADILMASI VƏ İCAZƏ DƏYİŞİKLİYİ QORUNMASI ---
@bot.event
async def on_guild_role_create(role):
  try:
    async for entry in role.guild.audit_logs(
        limit=1, action=discord.AuditLogAction.role_create
    ):
      if entry.user and entry.user.id != OWNER_ID and not entry.user.bot:
        member = role.guild.get_member(entry.user.id)
        if member and not member.guild_permissions.administrator:
          await role.delete(reason="Administrator və ya Sahibdən icazəsiz rol")
  except:
    pass


@bot.event
async def on_guild_role_update(before, after):
  try:
    async for entry in after.guild.audit_logs(
        limit=1, action=discord.AuditLogAction.role_update
    ):
      if entry.user and entry.user.id != OWNER_ID and not entry.user.bot:
        member = after.guild.get_member(entry.user.id)
        if (
            member
            and not member.guild_permissions.administrator
            and (after.permissions.administrator or after.permissions.manage_guild)
        ):
          await after.edit(
              permissions=before.permissions,
              reason="İcazəsiz səlahiyyət dəyişikliyi bloklandı!",
          )
  except:
    pass


# --- ANTİ-NUKE BAN QORUMASI ---
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
            t
            for t in ban_action_counts[actor.id]
            if current_time - t < TIME_WINDOW
        ]
        ban_action_counts[actor.id].append(current_time)

        if len(ban_action_counts[actor.id]) >= LIMIT:
          member = guild.get_member(actor.id)
          if member:
            try:
              await member.ban(
                  reason=f"{guild.name}: Anti-Nuke: İcazəsiz kütləvi ban"
              )
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
  dangerous_patterns = ["discord.gift/", "free-nitro", "steam-nitro", "nitro"]
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

  # 5. SƏRT UYARI İLƏ SPAM QORUMASI
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
      title="🛡️ Zona Təhlükəsizlik və İdarəetmə Sistemi",
      description="Serverin nizamını və intizamını qoruyur.",
      color=0x2b2d31,
  )
  embed.add_field(
      name="🎫 Şikayət Paneli Qur",
      value=(
          "!panel - Şikayət (bilet) açma düyməsini qeyd olunan kanala"
          " göndərir."
      ),
      inline=False,
  )
  embed.add_field(
      name="🎉 Çekiliş",
      value="!cekilis {dəqiqə} {hədiyyə} - Çekiliş başladır.",
      inline=False,
  )
  embed.add_field(
      name="📊 Sorğu", value="!sorğu {sual} - Səsvermə yaradır.", inline=False
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
      name="🔒 Kanal Kilidi / Lockdown",
      value=(
          "!lock / !unlock - Kanalı bağlayır/açır.\n!lockdown - Bütün serveri"
          " kilidləyir."
      ),
      inline=False,
  )
  embed.add_field(
      name="🧹 Təmizlik",
      value="!sil {say} | !siluser {@user} {say}",
      inline=False,
  )
  embed.add_field(
      name="⏱️ Slowmode & Ping", value="!slowmode {san} | !ping", inline=False
  )
  embed.set_footer(text=f"{ctx.guild.name} | Zona Security Systems")
  await ctx.send(embed=embed)


# Şikayət panelini həmin xüsusi ID-li kanala göndərir
@bot.command(name="panel")
async def panel(ctx):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  try:
    await ctx.message.delete()
    target_channel = bot.get_channel(TARGET_PANEL_CHANNEL_ID)
    if not target_channel:
      await ctx.send(
          "❌ Xəta: Şikayət kanalının ID-si tapılmadı!", delete_after=5
      )
      return

    embed = discord.Embed(
        title="🎫 Zona Dəstək və Şikayət Mərkəzi",
        description=(
            "Server ilə bağlı hər hansı bir şikayətiniz, sualınız və ya"
            " probleminiz varsa, aşağıdakı düyməyə basaraq bizimlə"
            " əlaqə saxlayın.\n\n*Düyməyə basan kimi yalnız sizinlə"
            " administratorun görə biləcəyi gizli kanal açılacaq!*"
        ),
        color=0x2b2d31,
    )
    embed.set_footer(text="Zona Security Systems")
    view = TicketButtonView()
    await target_channel.send(embed=embed, view=view)
    await ctx.send("✅ Şikayət paneli uğurla yerləşdirildi!", delete_after=3)
  except:
    pass


# ÇEKİLİŞ KOMANDASI (!cekilis dəqiqə hədiyyə)
@bot.command(name="cekilis")
async def cekilis(ctx, minutes: int, *, prize: str):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  try:
    await ctx.message.delete()
    embed = discord.Embed(
        title="🎉 YENİ ÇEKİLİŞ!",
        description=(
            f"Hədiyyə: **{prize}**\nQatılmaq üçün 🎉 emojisinə basın!"
            f"\nBitmə vaxtı: **{minutes} dəqiqə sonra**"
        ),
        color=0xFFD700,
    )
    embed.set_footer(
        text=f"Çekilişi başladan: {ctx.author.name} | Zona Systems"
    )

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
          f"🏆 **ÇEKİLİŞ BİTDİ!** Təbriklər {winner.mention}! Qazandığın"
          f" hədiyyə: **{prize}** 🎉"
      )
    else:
      await ctx.send("❌ Çekilişə heç kim qatılmadığı üçün qalib seçilmədi.")
  except:
    pass


# SORĞU KOMANDASI (!sorğu sual)
@bot.command(name="sorğu", aliases=["sorqu", "poll"])
async def sorqu(ctx, *, question: str):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return
  try:
    await ctx.message.delete()
    embed = discord.Embed(
        title="📊 Səsvermə / Sorğu",
        description=f"**Sual:** {question}",
        color=0x00AE86,
    )
    embed.set_footer(
        text=f"Sorğunu yaradan: {ctx.author.name} | Zona Systems"
    )

    msg = await ctx.send(embed=embed)
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")
  except:
    pass


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
      
