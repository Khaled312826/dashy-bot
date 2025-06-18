# File: doordash_account.py
import os
import json
import time
from faker import Faker
from dotenv import load_dotenv
import requests
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

load_dotenv()
SMS_API_KEY        = os.getenv('SMS_API_KEY')
SMSPOOL_SERVICE_ID = os.getenv('SMSPOOL_SERVICE_ID', '7727')
COOKIES_FILE       = 'doordash_cookies.json'
SMSPOOL_API_URL    = 'https://api.smspool.net/stubs/handler_api'


def allocate_temp_phone(country='US'):
    params = {
        'api_key': SMS_API_KEY,
        'action': 'order',
        'service': SMSPOOL_SERVICE_ID,
        'country': country
    }
    resp = requests.get(SMSPOOL_API_URL, params=params, timeout=10)
    text = resp.text.strip()
    if not text.startswith('ACCESS_NUMBER:'):
        raise RuntimeError(f"SMSPool error: {text}")
    _, order_id, phone = text.split(':', 2)
    return order_id, phone


def get_sms_code(order_id, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        params = {
            'api_key': SMS_API_KEY,
            'action': 'getStatus',
            'id': order_id
        }
        resp = requests.get(SMSPOOL_API_URL, params=params, timeout=10)
        text = resp.text.strip()
        if text.startswith('STATUS_OK:'):
            return text.split(':', 1)[1]
        time.sleep(5)
    raise TimeoutError('OTP not received')


async def create_doordash_account():
    fake = Faker()
    first_name = fake.first_name()
    last_name  = fake.last_name()
    email      = fake.email()
    password   = fake.password(length=12)

    order_id, phone = allocate_temp_phone()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page    = await context.new_page()

        # 1) Open DoorDash signup
        await page.goto('https://www.doordash.com/signup', wait_until='networkidle')

        # 2) Fill personal info
        await page.fill("input[placeholder='First Name']", first_name)
        await page.fill("input[placeholder='Last Name']", last_name)
        await page.fill("input[placeholder='Email']", email)

        # 3) Select country (+1 US)
        await page.click("button[aria-label='Country']")
        await page.click("li[data-value='+1']")

        # 4) Phone & password
        await page.fill("input[placeholder='Mobile Number']", phone)
        await page.fill("input[placeholder*='Password']", password)

        # 5) Submit sign-up
        await page.click("button:has-text('Sign Up')")

        # 6) Wait for OTP page and enter code
        # DoorDash uses a single field with placeholder like 'Enter 6-digit code'
        await page.wait_for_selector("input[placeholder*='6-digit']", timeout=30000)
        code = get_sms_code(order_id)
        await page.fill("input[placeholder*='6-digit']", code)
        # Click the submit button (labeled 'Submit' or similar)
        await page.click("button:has-text('Submit')")

        # 7) Save session cookies
        cookies = await context.cookies()
        with open(COOKIES_FILE, 'w') as f:
            json.dump(cookies, f)

        await browser.close()

    return {
        'phone': phone,
        'first_name': first_name,
        'last_name': last_name,
        'email': email
    }