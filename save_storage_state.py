# save_storage_state.py

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

async def save_state():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            executable_path=CHROME_PATH,
            headless=False
        )
        context = await browser.new_context()
        page = await context.new_page()

        # 1) Go to DoorDash home (Cloudflare runs)
        await page.goto("https://www.doordash.com", wait_until="domcontentloaded")
        print("🔄 Waiting for Cloudflare overlay to clear…")

        # 2) Wait for the CF overlay to go away.
        #    That overlay has data-testid="LAYER-MANAGER-MODAL"
        try:
            await page.wait_for_selector('[data-testid="LAYER-MANAGER-MODAL"]',
                                         state="detached",
                                         timeout=120_000)
        except TimeoutError:
            print("⚠️  Cloudflare didn’t clear in time—try again?")
            await browser.close()
            return

        # 3) Now that the overlay is gone, the “Sign In” button is clickable
        await page.wait_for_selector("text=Sign In", timeout=30_000)
        await page.click("text=Sign In")

        # 4) Let the user do the login + 2FA
        print("▶️  Please complete your login and 2FA in the browser…")
        # Now wait for the “Sign In” button to vanish (meaning you’re in)
        await page.wait_for_selector("text=Sign In", state="detached", timeout=300_000)

        # 5) Snapshot the fully-logged-in state
        Path("state.json").write_text(
            await context.storage_state()
        )
        print("✅  Saved storage state to state.json")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(save_state())
