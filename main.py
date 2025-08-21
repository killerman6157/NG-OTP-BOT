import asyncio
import re
from datetime import datetime, UTC
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import html
import os
from playwright.async_api import async_playwright
import json

import config
import db

# init db
db.init_db()

# aiogram bot
bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# playwright browser context
browser_context = None

# worker control
_worker_task = None
_worker_running = False

# =========================================================
# Logic don shiga da karɓar token ta Playwright
# =========================================================
async def login_and_fetch_token_playwright():
    print("Ana ƙoƙarin shiga da karɓar sabon zaman/token ta Playwright...")
    global browser_context
    try:
        if browser_context:
            await browser_context.close()
        
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        browser_context = await browser.new_context(
            user_agent=config.HEADERS['User-Agent']
        )
        page = await browser_context.new_page()
        
        await page.goto(config.LOGIN_URL, wait_until="networkidle")
        
        print("Playwright ya shiga shafin login.")
        
        # Jira har sai an gane Cloudflare kuma an wuce shi
        await page.wait_for_selector('input[name="_token"]', timeout=30000)
        
        initial_csrf_token = await page.input_value('input[name="_token"]')
        
        await page.fill('input[name="email"]', config.LOGIN_EMAIL)
        await page.fill('input[name="password"]', config.LOGIN_PASSWORD)
        
        await page.click('button[type="submit"]')
        
        print("An cike form kuma an danna 'login'.")
        
        await page.wait_for_url("**/portal/dashboard", timeout=30000)
        
        new_csrf_token = await page.input_value('input[name="_token"]')
        config.CSRF_TOKEN = new_csrf_token
        
        print("An shiga cikin nasara kuma an karɓi sabon CSRF token.")
        
        return True

    except Exception as e:
        db.save_error(f"Tsarin shiga ta Playwright ya kasa: {e}")
        print(f"Tsarin shiga ta Playwright ya kasa: {e}")
        return False

# masu taimakawa
def mask_number(num: str) -> str:
    s = num.strip()
    if len(s) <= (config.MASK_PREFIX_LEN + config.MASK_SUFFIX_LEN):
        return s
    return s[:config.MASK_PREFIX_LEN] + "****" + s[-config.MASK_SUFFIX_LEN:]

def detect_service(text: str) -> str:
    t = (text or "").lower()
    for k in sorted(config.SERVICES.keys(), key=len, reverse=True):
        if k in t:
            return config.SERVICES[k]
    return "Service"

def detect_country(number: str, extra_text: str = "") -> str:
    s = number.lstrip("+")
    for prefix, flagname in config.COUNTRY_FLAGS.items():
        if s.startswith(prefix):
            return flagname
    txt = (extra_text or "").upper()
    if "PERU" in txt:
        return config.COUNTRY_FLAGS.get("51", "🇵🇪 Peru")
    if "BANGLADESH" in txt or "+880" in number:
        return config.COUNTRY_FLAGS.get("880", "🇧🇩 Bangladesh")
    return "🌍 Unknown"

def extract_otps(text: str):
    return re.findall(r"\b(\d{4,8})\b", text or "")

def parse_html_response(html_text: str):
    soup = BeautifulSoup(html_text, "html.parser")
    return soup

async def fetch_once_playwright():
    entries = []
    global browser_context
    if not browser_context:
        print("Babu browser context. Ana ƙoƙarin sake shiga...")
        if not await login_and_fetch_token_playwright():
            return entries

    try:
        page = await browser_context.new_page()
        
        await page.goto(config.GET_SMS_URL, wait_until="networkidle")
        
        content = await page.content()
        ranges = []
        try:
            # Gwada a matsayin HTML
            soup = parse_html_response(content)
            for opt in soup.select("select#range option"):
                ranges.append(opt.get_text(strip=True))
        except Exception:
            # Gwada a matsayin JSON
            ranges = json.loads(content)
        
        if not ranges:
            ranges = [""]

        for rng in ranges:
            await page.goto(f"{config.GET_NUMBER_URL}?range={rng}", wait_until="networkidle")
            content2 = await page.content()
            numbers = []
            try:
                soup2 = parse_html_response(content2)
                for tr in soup2.select("table tr"):
                    tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                    for txt in tds:
                        m = re.search(r"(\+?\d{6,15})", txt)
                        if m:
                            numbers.append(m.group(1))
                            break
            except Exception:
                nums_json = json.loads(content2)
                for item in nums_json:
                    num = item.get("Number") or item.get("number")
                    if num:
                        numbers.append(str(num))

            for number in numbers:
                await page.goto(f"{config.GET_OTP_URL}?Number={number}&Range={rng}", wait_until="networkidle")
                content3 = await page.content()
                msgs_and_times = []
                try:
                    soup3 = parse_html_response(content3)
                    for tr in soup3.select("table tbody tr"):
                        tds = tr.find_all("td")
                        if len(tds) >= 3:
                            timestamp_str = tds[0].get_text(strip=True)
                            full_msg = tds[2].get_text(strip=True)
                            if timestamp_str and full_msg:
                                msgs_and_times.append({"message": full_msg, "fetched_at": timestamp_str})
                except Exception:
                    msgs_json = json.loads(content3)
                    for it in msgs_json:
                        text = it.get("sms") or it.get("message")
                        if text:
                            msgs_and_times.append({"message": text, "fetched_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")})

                for item in msgs_and_times:
                    m = item['message']
                    fetched_at = item['fetched_at']
                    otps = extract_otps(m)
                    if not otps:
                        continue
                    for otp in otps:
                        service = detect_service(m)
                        country = detect_country(number, rng)
                        entries.append({
                            "number": number,
                            "otp": otp,
                            "full_msg": m,
                            "service": service,
                            "country": country,
                            "range": rng,
                            "fetched_at": fetched_at
                        })
    except Exception as e:
        db.save_error(f"fetch_once_playwright exception: {e}")
        if browser_context:
            await browser_context.close()
        browser_context = None
    finally:
        if 'page' in locals() and not page.is_closed():
            await page.close()
    return entries

# Tsarin tura saƙo
async def forward_entry(e):
    num_display = mask_number(e["number"])
    
    full_msg_soup = BeautifulSoup(e.get('full_msg'), 'html.parser')
    message_content_tag = full_msg_soup.find('p', {'class': 'mb-0'})
    
    if message_content_tag:
        cleaned_full_msg = message_content_tag.get_text(strip=True)
    else:
        cleaned_full_msg = full_msg_soup.get_text(strip=True)
    
    if not cleaned_full_msg:
        cleaned_full_msg = e.get('full_msg')

    escaped_full_msg = html.escape(cleaned_full_msg)

    text = (
        f"<b>🔔 NEW OTP DETECTED</b> 🆕\n\n"
        f"⏰ <b>Time</b>: <blockquote><code>{e.get('fetched_at')}</code></blockquote>\n"
        f"🌍 <b>Country</b>: <blockquote><code>{e.get('country')}</code></blockquote>\n"
        f"⚙️ <b>Service</b>: <blockquote><code>{e.get('service')}</code></blockquote>\n"
        f"☎️ <b>Number</b>: <blockquote><code>{num_display}</code></blockquote>\n"
        f"🔑 <b>OTP</b>: <blockquote><code>{e.get('otp')}</code></blockquote>\n\n"
        f"📩 <b>Full Message</b>:\n<blockquote><code>{escaped_full_msg}</code></blockquote>\n\n"
        "Powered by 0xTeam"
    )
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Channel", url=config.CHANNEL_LINK),
         types.InlineKeyboardButton(text="Developer", url="https://t.me/BashOnChain")]
    ])
    
    try:
        await bot.send_message(config.GROUP_ID, text, reply_markup=kb)
    except Exception as exc:
        db.save_error(f"Gabaɗayan saƙo ya kasa zuwa group: {exc}")
        try:
            await bot.send_message(config.ADMIN_ID, f"Gabaɗayan saƙo ya kasa: {exc}")
        except Exception:
            pass

# worker
async def worker():
    db.set_status("online")
    await bot.send_message(config.ADMIN_ID, "✅ Worker ya fara aiki.")
    global _worker_running
    _worker_running = True
    while _worker_running:
        entries = await fetch_once_playwright()
        for e in entries:
            if not db.otp_exists(e["number"], e["otp"]):
                db.save_otp(e["number"], e["otp"], e["full_msg"], e["service"], e["country"])
                await forward_entry(e)
        await asyncio.sleep(config.FETCH_INTERVAL)
    db.set_status("offline")
    await bot.send_message(config.ADMIN_ID, "🛑 Worker ya daina aiki.")

def stop_worker_task():
    global _worker_running, _worker_task
    if not _worker_running:
        return
    _worker_running = False
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()

# commands
@dp.message(F.text == "/start")
async def cmd_start(m: types.Message):
    if m.from_user.id != config.ADMIN_ID:
        await m.answer("⛔ Ba ka da izini.")
        return
    st = db.get_status()
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="▶️ Fara", callback_data="start_worker"),
         types.InlineKeyboardButton(text="⏸ Tsaya", callback_data="stop_worker")],
        [types.InlineKeyboardButton(text="🧹 Share DB", callback_data="clear_db"),
         types.InlineKeyboardButton(text="❗ Kurakurai", callback_data="show_errors")],
        [types.InlineKeyboardButton(text="🔄 Sake shiga", callback_data="relogin")]
    ])
    await m.answer(f"⚙️ <b>OTP Receiver</b>\nStatus: <b>{st}</b>\nStored OTPs: <b>{db.count_otps()}</b>", reply_markup=kb)

@dp.callback_query()
async def cb(q: types.CallbackQuery):
    if q.from_user.id != config.ADMIN_ID:
        await q.answer("⛔ Ba ka da izini", show_alert=True)
        return
    if q.data == "start_worker":
        global _worker_task
        if _worker_task is None or _worker_task.done():
            _worker_task = asyncio.create_task(worker())
            await q.message.answer("✅ Worker ya fara aiki.")
        else:
            await q.message.answer("ℹ️ Worker yana aiki tuni.")
        await q.answer()
    elif q.data == "stop_worker":
        stop_worker_task()
        await q.message.answer("🛑 Worker yana tsayawa...")
        await q.answer()
    elif q.data == "clear_db":
        db.clear_otps()
        await q.message.answer("🗑 OTP DB an share shi.")
        await q.answer()
    elif q.data == "show_errors":
        rows = db.get_errors(10)
        if not rows:
            await q.message.answer("✅ Babu kurakurai da aka rubuta.")
        else:
            text = "\n\n".join([f"{r[1]} — {r[0]}" for r in rows])
            await q.message.answer(f"<b>Kurakurai na ƙarshe</b>:\n\n{text}")
        await q.answer()
    elif q.data == "relogin":
        if await login_and_fetch_token_playwright():
            await q.message.answer("✅ Sake shiga na hannu ya yi nasara!")
        else:
            await q.message.answer("❌ Sake shiga na hannu ya kasa! Duba logs.")
        await q.answer()

@dp.message(F.text == "/on")
async def cmd_on(m: types.Message):
    if m.from_user.id != config.ADMIN_ID:
        await m.answer("⛔ Ba ka da izini.")
        return
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(worker())
        await m.answer("✅ Worker ya fara aiki.")
    else:
        await m.answer("ℹ️ Worker yana aiki tuni.")

@dp.message(F.text == "/off")
async def cmd_off(m: types.Message):
    if m.from_user.id != config.ADMIN_ID:
        await m.answer("⛔ Ba ka da izini.")
        return
    stop_worker_task()
    await m.answer("🛑 Worker yana tsayawa...")

@dp.message(F.text == "/status")
async def cmd_status(m: types.Message):
    if m.from_user.id != config.ADMIN_ID:
        await m.answer("⛔ Ba ka da izini.")
        return
    await m.answer(f"📡 Status: <b>{db.get_status()}</b>\n📥 OTPs da aka ajiye: <b>{db.count_otps()}</b>")

@dp.message(F.text == "/check")
async def cmd_check(m: types.Message):
    if m.from_user.id != config.ADMIN_ID:
        await m.answer("⛔ Ba ka da izini.")
        return
    await m.answer(f"OTPs da aka ajiye: <b>{db.count_otps()}</b>")

@dp.message(F.text == "/clear")
async def cmd_clear(m: types.Message):
    if m.from_user.id != config.ADMIN_ID:
        await m.answer("⛔ Ba ka da izini.")
        return
    db.clear_otps()
    await m.answer("🗑 OTP DB an share shi.")

@dp.message(F.text == "/errors")
async def cmd_errors(m: types.Message):
    if m.from_user.id != config.ADMIN_ID:
        await m.answer("⛔ Ba ka da izini.")
        return
    rows = db.get_errors(20)
    if not rows:
        await m.answer("✅ Babu kurakurai da aka rubuta.")
    else:
        text = "\n\n".join([f"{r[1]} — {r[0]}" for r in rows])
        await m.answer(f"<b>Kurakurai na ƙarshe</b>:\n\n{text}")

async def on_startup():
    print("Ana ƙoƙarin shiga da karɓar sabon zaman/token a farkon aiki.")
    if await login_and_fetch_token_playwright():
        print("Shiga na farko ya yi nasara.")
    else:
        print("Shiga na farko ya kasa. Bot bazai iya aiki yadda ya kamata ba.")
        db.save_error("Shiga na farko ya kasa. Bot bazai iya aiki yadda ya kamata ba.")

    if db.get_status() == "online":
        global _worker_task
        _worker_task = asyncio.create_task(worker())

if __name__ == "__main__":
    try:
        import logging
        logging.basicConfig(level=logging.INFO)
        dp.startup.register(on_startup)
        dp.run_polling(bot)
    except KeyboardInterrupt:
        print("Fita...")
