import os
import re
import json
import asyncio
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Configuration
COOKIES_FILE = 'doordash_cookies.json'
PROMO_CODE = os.getenv('PROMO_CODE', '')

async def place_doordash_order_async(group_link: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        # Load existing session cookies if available
        if os.path.exists(COOKIES_FILE):
            cookies = json.load(open(COOKIES_FILE))
            await context.add_cookies(cookies)
        page = await context.new_page()
        # Navigate to group order link
        await page.goto(group_link, wait_until='networkidle')
        # Review order
        await page.wait_for_selector("button[data-test='review-order-button']", timeout=20000)
        await page.click("button[data-test='review-order-button']", timeout=10000)
        # Apply promo code if provided
        if PROMO_CODE:
            try:
                await page.wait_for_selector("button[data-test='promo-toggle']", timeout=5000)
                await page.click("button[data-test='promo-toggle']")
                await page.fill("input[name='promoCode']", PROMO_CODE)
                await page.click("button[data-test='apply-promo']")
                await page.wait_for_timeout(1000)
            except PlaywrightTimeoutError:
                pass
        # Complete the order
        await page.click("button[data-test='complete-order']", timeout=20000)
        # Wait for confirmation PIN
        await page.wait_for_selector("span[data-test='confirmation-pin']", timeout=20000)
        raw_pin = await page.inner_text("span[data-test='confirmation-pin']")
        pin = raw_pin.strip() if raw_pin else None
        # Extract order ID from URL
        order_url = page.url
        order_id = None
        m = re.search(r'/orders/(\d+)', order_url)
        if m:
            order_id = m.group(1)
        # Attempt to get driver phone
        driver_phone = None
        try:
            dp = await page.inner_text(".driver-phone")
            driver_phone = dp.strip() if dp else None
        except:
            pass
        # Save updated cookies
        cookies = await context.cookies()
        with open(COOKIES_FILE, 'w') as f:
            json.dump(cookies, f)
        await browser.close()
        return {'pin': pin, 'order_id': order_id, 'driver_phone': driver_phone}

def place_doordash_order(group_link: str) -> dict:
    return asyncio.run(place_doordash_order_async(group_link))
