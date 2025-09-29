import discord
import aiohttp
import asyncio
import os
from discord.ext import tasks
from datetime import datetime, timezone

TOKEN = os.getenv("TOKEN")
CHANNEL_ID = 1405889445382721557
ROLE_ID = 1412140353506639953
CHECK_URL = "https://www.supermechs.com/"
EXPECTED_STATUS = 200
CHECK_INTERVAL = 20

intents = discord.Intents.default()
client = discord.Client(intents=intents)

last_status = None
downtime_start = None
session = None
consecutive_failures = 0

async def send_and_publish(channel, text, mention_role=False):
    if mention_role:
        role = channel.guild.get_role(ROLE_ID)
        if role:
            text = f"{role.mention} {text}"
        else:
            print(f"❌ Could not find role with ID {ROLE_ID}")

    message = await channel.send(text)
    if channel.type.name == "news":
        try:
            await message.publish()
            print("📢 Published announcement.")
        except discord.Forbidden:
            print("❌ Bot lacks permission to publish messages.")
        except discord.HTTPException as e:
            print(f"❌ Failed to publish message: {e}")

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_server():
    global last_status, downtime_start, session, consecutive_failures
    try:
        channel = await client.fetch_channel(CHANNEL_ID)
    except discord.Forbidden:
        print(f"❌ Bot has no access to channel {CHANNEL_ID}")
        return
    except Exception as e:
        print(f"❌ Failed to fetch channel: {e}")
        return

    try:
        async with session.get(CHECK_URL, timeout=15) as resp:
            is_up = (resp.status == EXPECTED_STATUS)
            print(f"[Ping] Server returned {resp.status} — {'UP' if is_up else 'DOWN'}")

            if is_up:
                if last_status is False:
                    downtime_end = datetime.now(timezone.utc)
                    downtime_duration = downtime_end - downtime_start if downtime_start else None
                    downtime_minutes = int(downtime_duration.total_seconds() / 60) if downtime_duration else 0

                    await send_and_publish(
                        channel,
                        f"✅ Super Mechs is back ONLINE! Downtime was approximately {downtime_minutes} minutes.",
                        mention_role=True
                    )

                consecutive_failures = 0
                downtime_start = None
                last_status = True

            else:
                consecutive_failures += 1
                print(f"[Ping] Failure count: {consecutive_failures}")

                if consecutive_failures == 1 and downtime_start is None:
                    downtime_start = datetime.now(timezone.utc)

                if consecutive_failures == 3:
                    await send_and_publish(
                        channel,
                        f"⚠️ Super Mechs appears to be DOWN (confirmed after 3 checks).",
                        mention_role=True
                    )
                    last_status = False

    except asyncio.TimeoutError:
        print("[Ping] Server timed out")
        consecutive_failures += 1

        if consecutive_failures == 1 and downtime_start is None:
            downtime_start = datetime.now(timezone.utc)

        if consecutive_failures == 3:
            await send_and_publish(channel, "⚠️ Super Mechs is DOWN (3 consecutive timeouts).", mention_role=True)
            last_status = False

    except Exception as e:
        print(f"[Ping] Error checking server: {e}")
        consecutive_failures += 1

        if consecutive_failures == 1 and downtime_start is None:
            downtime_start = datetime.now(timezone.utc)

        if consecutive_failures == 3:
            await send_and_publish(channel, f"❌ Error checking Super Mechs (3 times): {e}", mention_role=True)
            last_status = False

@client.event
async def on_ready():
    global session
    print(f"✅ Logged in as {client.user}")
    session = aiohttp.ClientSession()
    check_server.start()

@client.event
async def on_close():
    global session
    if session:
        await session.close()

client.run(TOKEN)
