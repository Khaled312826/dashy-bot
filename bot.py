import os
import json
import re
import asyncio
import random
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import httpx

from doordash_account import create_doordash_account
from doordash_auto_order import place_doordash_order

print("Hello from bot.py!")  # sanity check that your script is running

# ─── Config & Persistence ─────────────────────────────────────────
load_dotenv()
TOKEN              = os.getenv("BOT_TOKEN")
BOT_USERNAME       = os.getenv("BOT_USERNAME")
CHASE_USER         = os.getenv("CHASE_USER")
CHASE_PASS         = os.getenv("CHASE_PASS")
CHASE_ZELLE_URL    = os.getenv(
    "CHASE_ZELLE_URL",
    "https://secure.chase.com/web/auth/dashboard#/dashboard/quickPay/paymentsActivity/index;params=qp,receivedactivity"
)
SMSPOOL_API_KEY    = os.getenv("SMSPOOL_API_KEY", os.getenv("SMS_API_KEY"))
SMSPOOL_SERVICE_ID = os.getenv("SMSPOOL_SERVICE_ID")

ZELLE_NUMBER  = os.getenv("ZELLE_NUMBER", "9096829298")
ZELLE_LINK    = f"https://zellepay.com/send?recipient={ZELLE_NUMBER}"
DASHY_FEE     = float(os.getenv("DASHY_FEE", "3.50"))
MIN_ORDER     = float(os.getenv("MIN_ORDER", "15.00"))

USERS_FILE     = Path("users.json")
REFERRALS_FILE = Path("referrals.json")
STATE_FILE     = Path("state.json")

users_data     = json.loads(USERS_FILE.read_text())     if USERS_FILE.exists()     else {}
referrals_data = json.loads(REFERRALS_FILE.read_text()) if REFERRALS_FILE.exists() else {}
seen_start     = set()

# ─── SMSPool (“SMS-activate”) Helpers ──────────────────────────────
SMSPOOL_BASE = "https://api.smspool.net/stubs/handler_api"

async def reserve_number(service: str = "DOORDASH", country: str = "US", pool: str = "default") -> tuple[str,str]:
    params = {
        "api_key": SMSPOOL_API_KEY,
        "action":  "getNumber",
        "service": service,
        "country": country,
        "pool":    pool
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(SMSPOOL_BASE, params=params)
        r.raise_for_status()
        resp = r.text.strip()
    if not resp.startswith("ACCESS_NUMBER"):
        raise RuntimeError(f"SMSPool reserve failed: {resp}")
    _, sms_id, phone = resp.split(":", 2)
    print(f"🆔 Reserved SMS id={sms_id}, phone={phone}")
    return sms_id, phone

async def poll_for_code(sms_id: str, timeout: int = 120) -> str:
    deadline = asyncio.get_event_loop().time() + timeout
    params = {
        "api_key": SMSPOOL_API_KEY,
        "action":  "getStatus",
        "id":      sms_id
    }
    async with httpx.AsyncClient() as client:
        while asyncio.get_event_loop().time() < deadline:
            r = await client.get(SMSPOOL_BASE, params=params)
            r.raise_for_status()
            resp = r.text.strip()
            if resp.startswith("STATUS_OK"):
                code = resp.split(":",1)[1]
                print(f"✉️ Got SMS code: {code}")
                return code
            await asyncio.sleep(5)
    raise RuntimeError("Timed out waiting for SMS code")

async def release_number(sms_id: str):
    params = {
        "api_key": SMSPOOL_API_KEY,
        "action":  "setStatus",
        "id":      sms_id,
        "status":  "6"
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(SMSPOOL_BASE, params=params)
        r.raise_for_status()
        print(f"🗑️ Released SMS id={sms_id}, resp={r.text.strip()}")

# ─── DoorDash Account Creation (with SMS-activate) ─────────────────
async def create_doordash_account_with_sms():
    sms_id, phone = await reserve_number()
    try:
        result = await create_doordash_account(
            phone_number=phone,
            get_sms_code=lambda: poll_for_code(sms_id)
        )
        print("✅ DoorDash account created:", result)
        return result
    except Exception as e:
        print("❌ DoorDash account creation failed:", e)
        raise
    finally:
        await release_number(sms_id)

# ─── Human-like typing helper ──────────────────────────────────────
async def human_type(page, selector: str, text: str):
    for ch in text:
        await page.type(selector, ch, delay=random.randint(80,150))

# ─── Playwright Persistent Context (basic) ─────────────────────────
PROFILE_DIR        = Path(__file__).parent / "chrome_automate_profile"
PROFILE_DIR.mkdir(exist_ok=True)
CHROME_USER_DATA   = str(PROFILE_DIR)
CHROME_PROFILE_DIR = os.getenv("CHROME_PROFILE_DIR", "Default")

async def get_persistent_context(headless: bool = True):
    pw  = await async_playwright().start()
    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=CHROME_USER_DATA,
        channel="chrome",
        headless=headless,
        args=[f"--profile-directory={CHROME_PROFILE_DIR}", "--disable-blink-features=AutomationControlled"]
    )
    await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    return ctx

# ─── Utilities ─────────────────────────────────────────────────────
def parse_price(text: str) -> float:
    try:
        return float(re.sub(r"[^\d.]", "", text))
    except:
        return 0.0

# ─── DoorDash Scraping ──────────────────────────────────────────────
async def extract_order_details(url: str) -> dict:
    ctx  = await get_persistent_context(headless=False)
    page = await ctx.new_page()
    await page.goto(url, wait_until="networkidle")
    restaurant = await page.text_content("h1[data-anchor-id='RestaurantName']") or "Unknown"
    address    = await page.text_content("div[data-anchor-id='DeliveryAddress']") or "Unknown"
    items      = [(await n.text_content() or "").strip()
                  for n in await page.query_selector_all("[data-anchor-id='OrderedItem']")]
    orig    = parse_price(await page.text_content("[data-anchor-id='Subtotal'] span") or "0")
    disc_el = await page.query_selector("span.discounted, .discounted-price")
    discounted = parse_price(await disc_el.text_content()) if disc_el else orig
    await ctx.close()
    return {
        "restaurant": restaurant.strip(),
        "address":    address.strip(),
        "items":      items,
        "original":   orig,
        "discounted": discounted
    }

# ─── Chase/Zelle Payment Check ────────────────────────────────────
async def check_chase_for(amount: float) -> bool:
    ctx  = await get_persistent_context(headless=False)
    page = await ctx.new_page()
    page.set_default_timeout(60000)
    page.set_default_navigation_timeout(60000)

    # 1) Login
    print("🔐 Chase: login…")
    await page.goto(
        "https://secure.chase.com/web/auth/?treatment=chase#/logon/logon/chaseOnline",
        wait_until="load"
    )
    await page.wait_for_selector("input[type='password']", timeout=30000)
    await human_type(page, "input[type='password']", CHASE_PASS)
    await page.click("button:has-text('Sign in')")
    print("✅ Chase initial login submitted.")

    # 2) Go to Zelle
    print(f"🌐 Chase: go to {CHASE_ZELLE_URL}")
    await page.goto(CHASE_ZELLE_URL, wait_until="load")

    # 3) Re-login prompt
    print("🔄 Chase: re-login via TAB→password→ENTER…")
    await page.wait_for_load_state("networkidle")
    await page.keyboard.press("Tab")
    await human_type(page, "", CHASE_PASS)
    await page.keyboard.press("Enter")
    print("✅ Chase re-login submitted.")

    # 4) Wait for table rows
    print("⌛ Chase: waiting for table rows…")
    await page.wait_for_selector("table tbody tr", timeout=60000)
    await asyncio.sleep(1)

    # 5) Scan
    for i in range(24):
        rows = await page.query_selector_all("table tbody tr")
        print(f"🔍 Chase attempt {i+1}: {len(rows)} rows")
        for row in rows:
            txt = (await row.text_content() or "").strip()
            if f"${amount:.2f}" in txt and "Completed" in txt:
                print("🎉 Chase: payment found!")
                await ctx.close()
                return True
        print("↻ Chase: not found, retry in 5s…")
        await asyncio.sleep(5)
        await page.reload()

    print("❌ Chase: no matching payment.")
    await ctx.close()
    return False

# ─── Monitor & Place ───────────────────────────────────────────────
async def monitor_and_place(amount: float, link: str, bot, chat_id: int, msg_id: int):
    if not await check_chase_for(amount):
        return await bot.send_message(chat_id, "❌ Payment not detected, order expired.")
    # **only change**: use SMS-powered signup when STATE_FILE missing
    if not STATE_FILE.exists():
        try:
            await create_doordash_account_with_sms()
        except:
            return await bot.send_message(chat_id, "❌ DoorDash signup failed.")
    try:
        res = place_doordash_order(link)
        pin, oid, tel = res["pin"], res["order_id"], res["driver_phone"]
        await bot.delete_message(chat_id, msg_id)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚚 Track Order", web_app=WebAppInfo(
                url=f"https://your-domain.com/tracking.html?order_id={oid}"
            ))],
            [InlineKeyboardButton("📞 Call Driver", url=f"tel:{tel}")]
        ])
        await bot.send_message(
            chat_id,
            f"✅ Order placed! PIN *{pin}*",
            parse_mode="Markdown",
            reply_markup=kb
        )
    except Exception as e:
        print("❌ Order placement failed:", e)
        await bot.send_message(chat_id, "❌ Unable to place DoorDash order.")

# ─── Telegram Handlers ─────────────────────────────────────────────
async def handle_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not any(x in text for x in ("doordash.com/group-orders/","drd.sh/cart/")):
        return
    det, orig, disc = await extract_order_details(text), None, None
    orig, disc = det["original"], det["discounted"]
    total     = round(disc + DASHY_FEE, 2)
    if total < MIN_ORDER:
        return await update.message.reply_text(f"🚫 Minimum ${MIN_ORDER:.2f}. Your total: ${total:.2f}")
    items   = "\n• ".join(det["items"])
    savings = round(orig - total, 2)
    pct     = round((savings/orig)*100,1) if orig else 0
    summary = (
        f"*{det['restaurant']}*\n{det['address']}\n\n"
        f"Items:\n• {items}\n\n"
        f"Original: ${orig:.2f}\n"
        f"_Discount -${orig-disc:.2f}_\n*Total: ${total:.2f}*\n"
        f"_You saved ${savings:.2f} ({pct}% off)_"
    )
    pending = await update.message.reply_text(
        summary, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💸 Pay Now", url=ZELLE_LINK)]])
    )
    asyncio.create_task(monitor_and_place(total, text, ctx.bot,
                                         update.effective_chat.id, pending.message_id))

async def start_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if ctx.args and ctx.args[0] != uid and uid not in referrals_data:
        referrals_data[uid] = ctx.args[0]
        REFERRALS_FILE.write_text(json.dumps(referrals_data, indent=4))
        users_data.setdefault(ctx.args[0], 0)
        USERS_FILE.write_text(json.dumps(users_data, indent=4))
    if uid not in seen_start:
        seen_start.add(uid)
        await update.message.reply_text("👋 Welcome! Send a DoorDash link to start.")
    else:
        await update.message.reply_text("Send another DoorDash link anytime.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    print("✅ Bot is up and running — waiting for messages…")
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.run_polling()

if __name__ == "__main__":
    main()
