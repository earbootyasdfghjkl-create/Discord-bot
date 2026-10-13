

import datetime
import os
from collections import defaultdict
import re
from threading import Thread
import time
import discord
from discord.ext import commands
from flask import Flask

# --- RENDER PORT HATASINI ÖNLEMEK İÇİN FLASK SERVER ---
app = Flask('')


@app.route('/')
def home():
  return 'ALLAHSİZ Bot aktivdir!'


def run():
  app.run(host='0.0.0.0', port=8080)


def keep_alive():
  t = Thread(target=run)
  t.start()


# --- DİSCORD BOT AYARLARI ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.webhooks = True
intents.guilds = True
intents.moderation = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', help_command=None, intents=intents)

# Sahib ID-si və 7/24 Səs Kanalı ID-si
OWNER_ID = 641014966312501259
VOICE_CHANNEL_ID = 1507834544756101302

anti_spam_status = {}
user_message_counts = defaultdict(list)
user_last_message = {}
ban_action_counts = defaultdict(list)

# XƏBƏRDARLIQ SAYĞACLARI
caps_warnings = defaultdict(int)
long_text_warnings = defaultdict(int)
repeat_warnings = defaultdict(int)


def clean_text(text):
  text = text.lower()
  replacements = {
      '4': 'a',
      '@': 'a',
      '3': 'e',
      '1': 'i',
      '!': 'i',
      '0': 'o',
      '5': 's',
      '$': 's',
      '7': 't',
      '+': 't',
      '8': 'b',
      '9': 'g',
  }
  for char, replacement in replacements.items():
    text = text.replace(char, replacement)
  return text.replace(' ', '')


# --- BOT HAZIR OLDUQDA VƏ SƏSƏ QOŞULDUQDA ---
@bot.event
async def on_ready():
  activity = discord.Activity(
      type=discord.ActivityType.watching, name='ALLAHSİZ Təhlükəsizlik 🛡️'
  )
  await bot.change_presence(activity=activity)
  print(f'ALLAHSİZ Təhlükəsizlik Botu tam aktivdir: {bot.user}')

  # 7/24 Səs Kanalına Qoşulma
  try:
    channel = bot.get_channel(VOICE_CHANNEL_ID)
    if channel and isinstance(channel, discord.VoiceChannel):
      await channel.connect(reconnect=True, self_deaf=True)
      print(f'Bot {channel.name} səs kanalına 7/24 daxil oldu!')
  except Exception as e:
    print(f'Səs kanalına qoşularkən xəta baş verdi: {e}')


# --- ƏGƏR SƏS KANALINDAN ÇIXARILARSA AVTOMATİK GERİ QOŞULMA ---
@bot.event
async def on_voice_state_update(member, before, after):
  if member.id == bot.user.id and after.channel is None:
    try:
      channel = bot.get_channel(VOICE_CHANNEL_ID)
      if channel and isinstance(channel, discord.VoiceChannel):
        await channel.connect(reconnect=True, self_deaf=True)
        print('Bot səs kanalına yenidən avtomatik daxil oldu!')
    except Exception as e:
      print(f'Səsə avtomatik geri qoşulma xətası: {e}')


# --- SAXTA HESAB VƏ BOT QORUNMASI ---
@bot.event
async def on_member_join(member):
  try:
    now = discord.utils.utcnow()
    account_age = (now - member.created_at).total_seconds()

    if account_age < 86400 and not member.avatar:
      await member.kick(
          reason='ALLAHSİZ Anti-Bot: Şübhəli / Yeni yaradılmış saxta hesab.'
      )
  except:
    pass


# --- 1. WEBHOOK QORUNMASI ---
@bot.event
async def on_webhooks_update(channel):
  try:
    async for entry in channel.guild.audit_logs(
        limit=1, action=discord.AuditLogAction.webhook_create
    ):
      if entry.user and entry.user.id != OWNER_ID:
        member = channel.guild.get_member(entry.user.id)
        if member and not member.guild_permissions.administrator:
          pass
  except:
    pass


# --- 2. KANAL YARADILMASI QORUNMASI (Adminlər və Sahib yarada bilər) ---
@bot.event
async def on_guild_channel_create(channel):
  try:
    async for entry in channel.guild.audit_logs(
        limit=1, action=discord.AuditLogAction.channel_create
    ):
      if entry.user and entry.user.id != OWNER_ID:
        member = channel.guild.get_member(entry.user.id)
        if member and not member.guild_permissions.administrator:
          await channel.delete(
              reason=f'{channel.guild.name}: Administrator və ya Sahibdən başqasına kanal açmaq qadağandır!'
          )
  except:
    pass


# --- 3. ROL YARADILMASI QORUNMASI (Adminlər və Sahib yarada bilər) ---
@bot.event
async def on_guild_role_create(role):
  try:
    async for entry in role.guild.audit_logs(
        limit=1, action=discord.AuditLogAction.role_create
    ):
      if entry.user and entry.user.id != OWNER_ID:
        member = role.guild.get_member(entry.user.id)
        if member and not member.guild_permissions.administrator:
          await role.delete(
              reason=f'{role.guild.name}: Administrator və ya Sahibdən başqasına rol açmaq qadağandır!'
          )
  except:
    pass


# --- 4. ANTI-NUKE QORUNMASI ---
@bot.event
async def on_member_ban(guild, user):
  try:
    async for entry in guild.audit_logs(
        limit=1, action=discord.AuditLogAction.ban
    ):
      actor = entry.user
      if actor and actor.id != bot.user.id and actor.id != OWNER_ID:
        current_time = time.time()
        ban_action_counts[actor.id].append(current_time)

        ban_action_counts[actor.id] = [
            t for t in ban_action_counts[actor.id] if current_time - t < 10
        ]
        if len(ban_action_counts[actor.id]) > 3:
          member = guild.get_member(actor.id)
          if member:
            try:
              await member.ban(
                  reason=f'{guild.name}: Anti-Nuke: İcazəsiz kütləvi ban!'
              )
            except:
              pass
  except:
    pass


@bot.event
async def on_message(message):
  if message.author.bot:
    return

  if not message.guild:
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

  # --- HƏDDİNDƏN ARTIQ EMOJİ / SPAM QORUMASI ---
  emoji_count = len(re.findall(r'<a?:\w+:\d+>', content))
  if emoji_count > 5:
    try:
      await message.delete()
      warn_msg = await message.channel.send(
          f'{message.author.mention}, ANAVİ BACİVİ SİKDİM, emoji spamı'
          ' etmək qadağandır!'
      )
      await warn_msg.delete(delay=5)
      return
    except:
      pass

  # Zərərli link və fırıldaqçılıq qoruması
  dangerous_patterns = ['discord-gift', 'free-nitro', 'steam-nitro', 'dlcord.gg']
  if any(pattern in cleaned for pattern in dangerous_patterns):
    try:
      await message.delete()
      until = discord.utils.utcnow() + datetime.timedelta(minutes=1)
      await message.author.timeout(
          until, reason='ALLAHSİZ: Zərərli / Phishing link paylaşımı.'
      )
      warn_msg = await message.channel.send(
          f'{message.author.mention}, ANAVİ BACİVİ SİKDİM YAVAŞ YAZ, o nə'
          ' biçim linkdir elə?! 1 dəqiqəlik partlatdım səni!'
      )
      await warn_msg.delete(delay=5)
      return
    except Exception as e:
      print(f'Timeout error: {e}')

  # Kütləvi etiketləmə qoruması
  if message.mention_everyone or len(message.mentions) > 3:
    try:
      await message.delete()
      warn_msg = await message.channel.send(
          f'{message.author.mention}, ANAVİ BACİVİ SİKDİM, KİMİ ETİKETLƏRSƏN'
      )
      await warn_msg.delete(delay=5)
      return
    except:
      pass

  # Çox uzun mesaj qoruması (180 simvoldan çox)
  if len(content) > 180:
    try:
      await message.delete()
      long_text_warnings[message.author.id] += 1
      count = long_text_warnings[message.author.id]

      if count >= 3:
        long_text_warnings[message.author.id] = 0
        until = discord.utils.utcnow() + datetime.timedelta(minutes=1)
        await message.author.timeout(
            until, reason='Həddindən artıq uzun mesaj spamı.'
        )
        warn_msg = await message.channel.send(
            f'{message.author.mention}, ANAVİ BACİVİ SİKDİM, 3 DƏFƏDİR DASTAN'
            ' YAZIRSAN! Aldın 1 dəqiqəlik timeout-u!'
        )
        await warn_msg.delete(delay=5)
      else:
        warn_msg = await message.channel.send(
            f'{message.author.mention}, ANAVİ BACİVİ SİKDİM, BURADA ROMAN'
            f' YAZMIRIK! Uyarı: ({count}/3)'
        )
        await warn_msg.delete(delay=5)
      return
    except Exception as e:
      print(f'Timeout error: {e}')

  # --- CAPS LOCK QORUMASI ---
  is_random_laugh = any(
      x in cleaned
      for x in [
          'jsjs',
          'sjsj',
          'asj',
          'ksj',
          'djs',
          'hsd',
          'asd',
          'wjs',
          'swj',
          'jss',
      ]
  )
  if (
      not is_random_laugh
      and len(content) > 15
      and sum(1 for c in content if c.isupper()) / len(content) > 0.75
  ):
    try:
      await message.delete()
      caps_warnings[message.author.id] += 1
      count = caps_warnings[message.author.id]

      if count >= 3:
        caps_warnings[message.author.id] = 0
        until = discord.utils.utcnow() + datetime.timedelta(minutes=1)
        await message.author.timeout(until, reason='Caps Lock Spam.')
        warn_msg = await message.channel.send(
            f'{message.author.mention}, ANAVİ BACİVİ SİKDİM, QULAĞIMIZ'
            ' PARTLADI! 3 dəfədir qışqırırsan, aldın timeout!'
        )
        await warn_msg.delete(delay=5)
      else:
        warn_msg = await message.channel.send(
            f'{message.author.mention}, ANAVİ BACİVİ SİKDİM, NİYƏ QIŞQIRIRSAN'
            f" AMK, söndür o Caps'i! Uyarı: ({count}/3)"
        )
        await warn_msg.delete(delay=5)
      return
    except Exception as e:
      print(f'Timeout error: {e}')

  # --- REKLAM / LİNK QORUMASI ---
  link_patterns = [
      'discord.gg/',
      'discord.com/invite',
      'http://',
      'https://',
      't.me/',
  ]
  if any(domain in content.lower() for domain in link_patterns):
    try:
      await message.delete()
      warn_msg = await message.channel.send(
          f'{message.author.mention}, ANAVİ BACİVİ SİKDİM, BAŞQA SERVERİN'
          ' REKLamini GÖTÜMƏ SÜRTÜRSƏN? Bir də link atsan banı yeyəcəksən!'
      )
      await warn_msg.delete(delay=5)
      return
    except:
      pass

  # --- TƏKRAR MƏTN SPAM QORUMASI ---
  author_id = message.author.id
  current_time = time.time()

  if author_id not in user_message_counts:
    user_message_counts[author_id] = []

  last_msg = user_last_message.get(author_id, ('', 0))

  if (
      last_msg[0] == content or last_msg[0] == cleaned
  ) and current_time - last_msg[1] < 4:
    try:
      await message.delete()
      repeat_warnings[author_id] += 1
      count = repeat_warnings[author_id]

      if count >= 3:
        repeat_warnings[author_id] = 0
        until = discord.utils.utcnow() + datetime.timedelta(minutes=1)
        await message.author.timeout(until, reason='Tekrar Mesaj Spamı.')
        warn_msg = await message.channel.send(
            f'{message.author.mention}, ANAVİ BACİVİ SİKDİM, 3 DƏFƏDİR EYNİ ŞEYİ'
            ' ATIRSAN! Aldın 1 dəqiqəlik timeout!'
        )
        await warn_msg.delete(delay=5)
      else:
        warn_msg = await message.channel.send(
            f'{message.author.mention}, ANAVİ BACİVİ SİKDİM, EYNİ ŞEYİ'
            f' TƏKRAR-TƏKRAR ATMA! Uyarı: ({count}/3)'
        )
        await warn_msg.delete(delay=5)
      return
    except Exception as e:
      print(f'Timeout error: {e}')

  user_last_message[author_id] = (
      cleaned if len(cleaned) > 2 else content,
      current_time,
  )

  # Sürətli Mesaj Spamı
  user_message_counts[author_id] = [
      t for t in user_message_counts[author_id] if current_time - t < 5
  ]
  user_message_counts[author_id].append(current_time)

  if len(user_message_counts[author_id]) > 6:
    try:
      await message.delete()
      warn_msg = await message.channel.send(
          f'{message.author.mention}, ANAVİ BACİVİ SİKDİM, PUL PAYLAYIRLAR'
          ' MƏYƏR? Çox sürətli yazırsan, yavaş ol!'
      )
      await warn_msg.delete(delay=5)
      return
    except:
      pass

  await bot.process_commands(message)


# --- KOMANDALAR ---


@bot.command(name='yardim', aliases=['help'])
async def yardim(ctx):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return

  embed = discord.Embed(
      title='🛡️ ALLAHSİZ Təhlükəsizlik Sistemi',
      description='Serverin nizamını və intizamını qoruyur.',
      color=0x2b2d31,
  )
  embed.add_field(
      name='🔗 Dəvət Linki',
      value='`!url` - Serverin dəvət linkini göstərir.',
      inline=False,
  )
  embed.add_field(
      name='🛡️ Anti-Spam',
      value='`!antispam enable / disable` - Mühafizəni idarə edir.',
      inline=False,
  )
  embed.add_field(
      name='🔒 Kanal Kilidi',
      value='`!lock / !unlock` - Kanalı yazışmaya bağlayır/açır.',
      inline=False,
  )
  embed.add_field(
      name='🧹 Ümumi Təmizlik',
      value='`!sil [sayı]` - Göstərilən sayda mesajı təmizləyir.',
      inline=False,
  )
  embed.add_field(
      name='👤 İstifadəçiyə Özəl Təmizlik',
      value='`!siluser @istifadəçi [say]` - Müəyyən üzvün mesajlarını təmizləyir.',
      inline=False,
  )
  embed.add_field(
      name='⏱️ Yavaş Rejim / Slowmode',
      value='`!slowmode [saniyə]` - Kanala saniyə məhdudiyyəti qoyur.',
      inline=False,
  )
  embed.add_field(
      name='📊 Server Məlumatı',
      value='`!serverbilgisi` - Server haqqında məlumat verir.',
      inline=False,
  )
  embed.add_field(
      name='🏓 Gecikmə',
      value='`!ping` - Botun gecikmə sürətini yoxlayır.',
      inline=False,
  )
  embed.set_footer(text=f'{ctx.guild.name} • ALLAHSİZ Security Systems')
  await ctx.send(embed=embed)


@bot.command(name='antispam')
async def antispam(ctx, status: str):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return

  guild_id = ctx.guild.id
  if status.lower() == 'enable':
    anti_spam_status[guild_id] = True
    await ctx.send(f'✅ {ctx.guild.name}: Təhlükəsizlik sistemi aktivləşdirildi.')
  elif status.lower() == 'disable':
    anti_spam_status[guild_id] = False
    await ctx.send(f'⚠️ {ctx.guild.name}: Təhlükəsizlik sistemi söndürüldü.')
  else:
    await ctx.send(
        '❌ İstifadə qaydası: `!antispam enable` və ya `!antispam disable`'
    )


@bot.command(name='lock')
async def lock(ctx):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return

  try:
    await ctx.message.delete()
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(
        f'🔒 Bu kanal ({ctx.guild.name}) təhlükəsizlik protokolu ilə kilidləndi.',
        delete_after=5,
    )
  except:
    pass


@bot.command(name='unlock')
async def unlock(ctx):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return

  try:
    await ctx.message.delete()
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(
        f'🔓 Kanalın kilidi açıldı, ({ctx.guild.name}) sakinləri yenidən'
        ' yaza bilərsiniz.',
        delete_after=5,
    )
  except:
    pass


@bot.command(name='url')
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
          f'🔗 {ctx.guild.name} Dəvət Linki:'
          f' **discord.gg/{vanity.code}** (İstifadə: {vanity.uses})'
      )
    except:
      await ctx.send(
          f'🔗 {ctx.guild.name} Dəvət Linki:'
          f' **discord.gg/{ctx.guild.vanity_url_code}**'
      )
  else:
    await ctx.send(f'❌ {ctx.guild.name} Serverinin xüsusi (vanity) linki yoxdur.')


@bot.command(name='sil', aliases=['temizle'])
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
        f'🧹 **{len(deleted)}** ədəd mesaj təmizləndi.', delete_after=1
    )
  except:
    pass


@bot.command(name='siluser')
async def siluser(ctx, member: discord.Member, limit: int = 10):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return

  try:
    await ctx.message.delete()
    deleted = await ctx.channel.purge(
        limit=limit * 5, check=lambda m: m.author.id == member.id
    )
    await ctx.send(
        f'🧹 **{member.mention}** istifadəçisinin **{len(deleted)}** ədəd'
        ' mesajı təmizləndi.',
        delete_after=3,
    )
  except:
    await ctx.send('❌ Mesajlar silinərkən xəta baş verdi!', delete_after=3)


@bot.command(name='slowmode', aliases=['yavas'])
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
      await ctx.send('⏱️ Bu kanalda yavaş rejim **söndürüldü**.', delete_after=5)
    else:
      await ctx.send(
          f'⏱️ Bu kanalda yavaş rejim **{seconds} saniyə** olaraq tənzimləndi.',
          delete_after=5,
      )
  except:
    await ctx.send('❌ Yavaş rejim tətbiq edilərkən xəta baş verdi!', delete_after=5)


@bot.command(name='ping')
async def ping(ctx):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return

  latency = round(bot.latency * 1000)
  await ctx.send(f'🏓 Pong! Botun gecikmə sürəti: **{latency}ms**')


@bot.command(name='serverbilgisi')
async def serverbilgisi(ctx):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return

  guild = ctx.guild
  embed = discord.Embed(title=f'📊 {guild.name} - Server Məlumatı', color=0x2b2d31)
  embed.add_field(name='👑 Server Sahib(ə)si', value=f'{guild.owner}', inline=True)
  embed.add_field(name='👥 Üzv Sayı', value=guild.member_count, inline=True)
  embed.add_field(
      name='📅 Yaradılma Tarixi',
      value=guild.created_at.strftime('%d.%m.%Y'),
      inline=True,
  )
  await ctx.send(embed=embed)


@bot.command(name='ban')
async def ban(ctx, member: discord.Member, *, reason='Göstərilməyib'):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return

  try:
    await member.ban(reason=reason)
    await ctx.send(
        f'🔨 **{member}** serverdən uzaqlaşdırıldı. Səbəb: **{reason}**'
    )
  except:
    pass


@bot.command(name='kick')
async def kick(ctx, member: discord.Member, *, reason='Göstərilməyib'):
  if (
      ctx.author.id != OWNER_ID
      and not ctx.author.guild_permissions.administrator
  ):
    return

  try:
    await member.kick(reason=reason)
    await ctx.send(f'👢 **{member}** serverdən qovuldu. Səbəb: **{reason}**')
  except:
    pass


if __name__ == '__main__':
  keep_alive()
  bot.run(os.environ.get('DISCORD_TOKEN'))
      
