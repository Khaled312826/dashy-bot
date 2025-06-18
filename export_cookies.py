# save_as: export_cookies_playwright.py

import json
from pathlib import Path
from playwright.async_api import async_playwright

# Path to your real Chrome profile (Default)
USER_DATA_DIR = r"C:\Users\Hassa\AppData\Local\Google\Chrome\User Data"
PROFILE = "Default"

async def export_cookies(domain: str, outfile: str):
    # Launch Chrome in persistent mode so it's exactly your profile
    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            USER_DATA_DIR,
            channel="chrome",
            headless=True,      # you can make this False to watch it
            args=[
                f"--profile-directory={PROFILE}",
            ]
        )
        # Wait for the context to be “ready”
        page = await context.new_page()
        # Navigate to the domain so the cookies load
        await page.goto(f"https://{domain}", wait_until="networkidle")
        
        # Grab all cookies for that domain
        cookies = await context.cookies(f"https://{domain}")
        
        # Convert to Playwright→Playwright format (same as earlier)
        output = []
        for c in cookies:
            output.append({
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c["path"],
                "expires": c.get("expires"),      # might be None
                "httpOnly": c["httpOnly"],
                "secure": c["secure"],
                "sameSite": c.get("sameSite", "Lax"),
            })

        # Write out JSON
        Path(outfile).write_text(json.dumps(output, indent=2))
        print(f"Exported {len(output)} cookies to {outfile}")
        await context.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python export_cookies_playwright.py <domain> <outfile.json>")
        sys.exit(1)
    import asyncio
    asyncio.run(export_cookies(sys.argv[1], sys.argv[2]))
