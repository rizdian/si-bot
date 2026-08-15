from __future__ import annotations

import logging
import re
import asyncio
import json
import time

import aiohttp
import discord
from discord import app_commands

from config import (
    GUILD_ID,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_KEY_URL,
    OPENROUTER_FREE_MODEL,
    OPENROUTER_PAID_MODEL,
    AI_PERSONALITY,
    OWNER_USER_ID,
    WELCOME_PROMPT,
)

logger = logging.getLogger("bot")

TEST_GUILD = discord.Object(id=GUILD_ID)

AI_COOLDOWN_SECONDS = 10
AI_HISTORY_LIMIT = 2
AI_MAX_TOKENS = 350
AI_TIMEOUT_SECONDS = 60
AI_MAX_RETRIES = 2
AI_CONCURRENT_LIMIT = 4
MAX_PROMPT_LEN = 1000
MAX_HISTORY_MSG_LEN = 500
MAX_SYSTEM_LEN = 1500
EMBED_FIELD_LIMIT = 1024
MAX_REPLY_LEN = 4000
REPLY_CHUNK_LEN = 1900
STREAM_UPDATE_INTERVAL = 1.5

ai_cooldowns: dict[int, float] = {}

_welcome_cache: dict[str, str] = {}


def clean_text(text: str, limit: int = 1000) -> str:
    if not text:
        return ""

    text = text.strip()
    text = re.sub(r"\s+", " ", text)

    return text[:limit]


async def stream_openrouter(session: aiohttp.ClientSession, messages: list[dict[str, str]]):
    if not hasattr(session, "_openrouter_sem"):
        session._openrouter_sem = asyncio.Semaphore(AI_CONCURRENT_LIMIT)

    is_welcome = len(messages) == 2 and messages[0].get("content") == WELCOME_PROMPT
    cache_key = None
    if is_welcome:
        cache_key = messages[1].get("content")
        if cache_key in _welcome_cache:
            yield _welcome_cache[cache_key]
            return

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/si-bot",
        "X-Title": "Si-Bot Discord",
    }

    payload = {
        "model": OPENROUTER_FREE_MODEL,
        "messages": messages,
        "max_tokens": AI_MAX_TOKENS,
        "temperature": 0.8,
        "stream": True,
        "transforms": ["middle-out"],
    }

    retry_delay = 1.5

    full_reply_for_cache = ""
    fallback_used = False

    async with session._openrouter_sem:
        for attempt in range(1, AI_MAX_RETRIES * 2 + 1):
            phase_attempt = (attempt - 1) % AI_MAX_RETRIES + 1
            try:
                async with session.post(
                    OPENROUTER_BASE_URL,
                    headers=headers,
                    json=payload,
                    timeout=AI_TIMEOUT_SECONDS,
                ) as resp:
                    if resp.status == 429 or resp.status == 402:
                        if phase_attempt < AI_MAX_RETRIES:
                            header_retry = resp.headers.get("Retry-After")
                            try:
                                retry_delay = max(retry_delay, float(header_retry))
                            except (TypeError, ValueError):
                                pass
                            logger.warning("OpenRouter %s attempt=%s delay=%ss", resp.status, attempt, retry_delay)
                            await asyncio.sleep(min(retry_delay, 30))
                            retry_delay *= 2
                            continue

                        if not fallback_used:
                            payload["model"] = OPENROUTER_PAID_MODEL
                            fallback_used = True
                            logger.info("Free model gagal, switch ke paid: %s", OPENROUTER_PAID_MODEL)
                            retry_delay = 1.5
                            continue

                        if resp.status == 429:
                            yield "❌ Sabar Gw lagi Loading."
                            return
                        yield "❌ Kredit habis. Coba lagi nanti."
                        return

                    if resp.status != 200:
                        try:
                            data = await resp.json(content_type=None)
                            error_msg = data.get("error", {}).get("message", "Unknown error")
                        except Exception:
                            error_msg = await resp.text()
                        logger.error("OpenRouter error status=%s model=%s message=%s", resp.status, payload["model"], error_msg)
                        if not fallback_used:
                            payload["model"] = OPENROUTER_PAID_MODEL
                            fallback_used = True
                            logger.info("Free model failed, switching to paid: %s", OPENROUTER_PAID_MODEL)
                            continue
                        yield "❌ Lagi error dikit. Coba tag moderator aja."
                        return

                    async for line in resp.content:
                        line = line.decode("utf-8").strip()
                        if not line or line.startswith(":"):
                            continue

                        if line.startswith("data: "):
                            data_str = line[len("data: "):]
                            if data_str == "[DONE]":
                                break

                            try:
                                data = json.loads(data_str)
                                
                                # Check for mid-stream error
                                if "error" in data:
                                    error_msg = data["error"].get("message", "Unknown mid-stream error")
                                    logger.error("OpenRouter mid-stream error: %s", error_msg)
                                    yield f"\n\n[ERROR: {error_msg}]"
                                    return

                                usage = data.get("usage")
                                if usage:
                                    logger.info(
                                        "OpenRouter usage model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s cost=%s",
                                        data.get("model", payload["model"]),
                                        usage.get("prompt_tokens", 0),
                                        usage.get("completion_tokens", 0),
                                        usage.get("total_tokens", 0),
                                        usage.get("cost", "N/A"),
                                    )

                                choices = data.get("choices") or []
                                if choices:
                                    delta = choices[0].get("delta") or {}
                                    content = delta.get("content", "")
                                    if content:
                                        full_reply_for_cache += content
                                        yield content
                            except json.JSONDecodeError:
                                logger.error("Failed to parse SSE data: %s", line)
                                continue
                    
                    if is_welcome and cache_key and full_reply_for_cache:
                        _welcome_cache[cache_key] = full_reply_for_cache
                        if len(_welcome_cache) > 100:
                            _welcome_cache.pop(next(iter(_welcome_cache)))
                    return

            except asyncio.TimeoutError:
                logger.warning("OpenRouter timeout attempt=%s", attempt)
            except Exception:
                logger.exception("Failed calling OpenRouter attempt=%s", attempt)

            if attempt < AI_MAX_RETRIES:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            elif not fallback_used:
                payload["model"] = OPENROUTER_PAID_MODEL
                fallback_used = True
                logger.info("Free model timeout/error, switch ke paid: %s", OPENROUTER_PAID_MODEL)
                retry_delay = 1.5

    yield "❌ Bentar, lagi lag. Coba lagi nanti."


async def ask_openrouter(session: aiohttp.ClientSession, messages: list[dict[str, str]]) -> str:
    full_reply = ""
    async for chunk in stream_openrouter(session, messages):
        if chunk.startswith("[ERROR:"):
            logger.warning("OpenRouter mid-stream error in reply: %s", chunk)
            continue
        full_reply += chunk

    return full_reply or "❌ Kosong jawabannya. Aneh bat."


async def get_openrouter_key_info(session: aiohttp.ClientSession) -> dict | str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    }

    try:
        async with session.get(OPENROUTER_KEY_URL, headers=headers, timeout=10) as resp:
            if resp.status != 200:
                logger.error("OpenRouter key info error status=%s", resp.status)
                return f"❌ Gagal ambil info key. Status: {resp.status}"

            return await resp.json()
    except Exception:
        logger.exception("Failed calling OpenRouter key info")
        return "❌ Error pas mau ngecek limit."


async def build_user_history(channel: discord.abc.Messageable) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []

    async for msg in channel.history(limit=AI_HISTORY_LIMIT):
        if msg.author.bot:
            continue

        content = clean_text(msg.content, limit=MAX_HISTORY_MSG_LEN)
        if not content:
            continue

        history.append({"role": "user", "content": content})

    history.reverse()
    return history


async def build_member_context(interaction: discord.Interaction, prompt: str) -> str:
    if not interaction.guild:
        return ""

    context_parts = [
        f"- {interaction.user.display_name} adalah pengirim pesan saat ini."
    ]

    user_ids = set(re.findall(r"<@!?(\d+)>", prompt))

    for raw_user_id in user_ids:
        try:
            user_id = int(raw_user_id)
            member = interaction.guild.get_member(user_id)

            if not member:
                member = await interaction.guild.fetch_member(user_id)

            roles = [role.name.lower() for role in member.roles]

            category = "member umum"
            if any("admin" in role or "mod" in role for role in roles):
                category = "moderator/admin"
            elif any("boy" in role for role in roles):
                category = "boys"
            elif any("girl" in role for role in roles):
                category = "girls"

            context_parts.append(
                f"- {member.display_name} adalah {category}."
            )

        except Exception:
            logger.warning("Failed fetching mentioned member user_id=%s", raw_user_id)

    return "\n".join(context_parts)


def is_on_cooldown(user_id: int) -> tuple[bool, int]:
    now = time.monotonic()
    last_used = ai_cooldowns.get(user_id)

    if last_used and now - last_used > AI_COOLDOWN_SECONDS * 10:
        del ai_cooldowns[user_id]
        last_used = None

    if not last_used:
        ai_cooldowns[user_id] = now
        return False, 0

    elapsed = now - last_used
    if elapsed < AI_COOLDOWN_SECONDS:
        retry_after = int(AI_COOLDOWN_SECONDS - elapsed)
        return True, retry_after

    ai_cooldowns[user_id] = now
    return False, 0


async def build_chat_messages(interaction: discord.Interaction, prompt: str) -> list[dict[str, str]]:
    history = await build_user_history(interaction.channel)
    member_context = await build_member_context(interaction, prompt)

    system_content = AI_PERSONALITY
    if member_context:
        system_content += f"\n\nKonteks tambahan Discord:\n{member_context}"

    return [
        {"role": "system", "content": clean_text(system_content, limit=MAX_SYSTEM_LEN)},
        *history,
        {"role": "user", "content": prompt},
    ]


def build_chat_embed(prompt: str) -> discord.Embed:
    embed = discord.Embed(title="🤖 Langit Chat", color=discord.Color.green())
    embed.add_field(
        name="💬 Pertanyaan",
        value=prompt[:EMBED_FIELD_LIMIT] or "-",
        inline=False,
    )
    embed.add_field(name="🧠 Jawaban", value="Sedang berpikir...", inline=False)
    return embed


async def stream_reply_into_embed(
    message: discord.Message,
    embed: discord.Embed,
    session: aiohttp.ClientSession,
    messages: list[dict[str, str]],
) -> str:
    reply = ""
    last_update = time.monotonic()

    async for chunk in stream_openrouter(session, messages):
        reply += chunk

        now = time.monotonic()
        if now - last_update > STREAM_UPDATE_INTERVAL:
            display = clean_text(reply, limit=EMBED_FIELD_LIMIT) or "..."
            embed.set_field_at(1, name="🧠 Jawaban", value=display, inline=False)
            try:
                await message.edit(embed=embed)
            except discord.NotFound:
                break
            except Exception as e:
                logger.warning("Failed to update streaming message: %s", e)
            last_update = now

    return reply


async def finalize_reply_embed(message: discord.Message, embed: discord.Embed, reply: str) -> str:
    final_reply = clean_text(reply, limit=MAX_REPLY_LEN)
    display = final_reply[:EMBED_FIELD_LIMIT] or "❌ Kosong jawabannya."
    embed.set_field_at(1, name="🧠 Jawaban", value=display, inline=False)

    try:
        await message.edit(embed=embed)
    except discord.NotFound:
        pass
    except Exception as e:
        logger.warning("Failed final update of streaming message: %s", e)

    return final_reply


def register_ai_commands(tree: app_commands.CommandTree, client: discord.Client):
    @tree.command(
        name="chat",
        description="Tanya Langit (AI)",
        guild=TEST_GUILD,
    )
    @app_commands.describe(prompt="Pertanyaan atau pesan untuk Langit")
    async def chat(interaction: discord.Interaction, prompt: str) -> None:
        if not OPENROUTER_API_KEY:
            await interaction.response.send_message(
                "❌ API key OpenRouter belum dikonfigurasi.",
                ephemeral=True,
            )
            return

        user_id = interaction.user.id
        cooldown, retry_after = is_on_cooldown(user_id)

        if cooldown:
            await interaction.response.send_message(
                f"⚠️ Santai dikit napa, tunggu {retry_after} detik lagi.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            prompt = clean_text(prompt, limit=MAX_PROMPT_LEN)
            messages = await build_chat_messages(interaction, prompt)
            embed = build_chat_embed(prompt)

            message = await interaction.followup.send(embed=embed)
            reply = await stream_reply_into_embed(message, embed, client.ai_session, messages)
            final_reply = await finalize_reply_embed(message, embed, reply)

            if len(final_reply) > EMBED_FIELD_LIMIT:
                remaining = final_reply[EMBED_FIELD_LIMIT:]
                chunks = [
                    remaining[i:i + REPLY_CHUNK_LEN]
                    for i in range(0, len(remaining), REPLY_CHUNK_LEN)
                ]

                for chunk in chunks:
                    await interaction.followup.send(chunk)

        except Exception as e:
            logger.exception("Error saat menjalankan /chat")
            await interaction.followup.send(
                f"❌ Terjadi kesalahan: {e}",
                ephemeral=True,
            )

    @tree.command(
        name="limit",
        description="Cek sisa kredit dan limit OpenRouter",
        guild=TEST_GUILD,
    )
    async def limit(interaction: discord.Interaction) -> None:
        if interaction.user.id != OWNER_USER_ID:
            await interaction.response.send_message(
                "❌ Cuma owner yang boleh ngecek ginian.",
                ephemeral=True,
            )
            return

        if not OPENROUTER_API_KEY:
            await interaction.response.send_message(
                "❌ API key OpenRouter belum dikonfigurasi.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            res = await get_openrouter_key_info(client.ai_session)

            if isinstance(res, str):
                await interaction.followup.send(res)
                return

            data = res.get("data", {})
            label = data.get("label", "Unknown")
            limit_val = data.get("limit")
            usage = data.get("usage", 0)
            limit_remaining = data.get("limit_remaining")
            is_free_tier = data.get("is_free_tier", False)

            def format_credit(val):
                if val is None:
                    return "Unlimited"
                return f"${val:,.4f}"

            embed = discord.Embed(
                title="💳 OpenRouter Key Status",
                color=discord.Color.blue(),
            )
            embed.add_field(name="Label", value=label, inline=True)
            embed.add_field(name="Free Tier", value="Ya" if is_free_tier else "Bukan", inline=True)
            embed.add_field(name="Total Limit", value=format_credit(limit_val), inline=True)
            embed.add_field(name="Usage (All Time)", value=format_credit(usage), inline=True)
            embed.add_field(name="Sisa Kredit", value=format_credit(limit_remaining), inline=True)

            # Daily usage if available
            usage_daily = data.get("usage_daily", 0)
            embed.add_field(name="Usage Hari Ini", value=format_credit(usage_daily), inline=False)

            # Rate Limit Info
            # OpenRouter standard: 20 RPM for free/low tier. 
            # Paid users with $10+ credits get 1000 req/day on free models.
            rate_limit = data.get("rate_limit", {})
            if rate_limit:
                requests_limit = rate_limit.get("requests", "N/A")
                interval = rate_limit.get("interval", "N/A")
                embed.add_field(name="Rate Limit (Global)", value=f"{requests_limit} req / {interval}", inline=True)
            else:
                # Default info based on OpenRouter docs if rate_limit object is missing
                rpm_info = "20 RPM"
                rpd_info = "50 RPD (Free)" if is_free_tier else "1000 RPD (Paid-Free Tier)"
                embed.add_field(name="Rate Limit (Est.)", value=f"{rpm_info}, {rpd_info}", inline=True)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.exception("Error saat menjalankan /limit")
            await interaction.followup.send(f"❌ Error pas ngecek limit: {e}")