import json
import asyncio
from playwright.async_api import async_playwright

async def export_cookies_cdp(domain: str, outfile: str):
    async with async_playwright() as pw:
        # Connect to your already-running Chrome instance via CDP
        browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
        # Grab the first context (your persistent profile)
        context = browser.contexts[0]
        # Fetch cookies for your domain
        cookies = await context.cookies(f"https://{domain}")
        # Normalize and dump
        output = [
            {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c["path"],
                "expires": c.get("expires"),
                "httpOnly": c["httpOnly"],
                "secure": c["secure"],
                "sameSite": c.get("sameSite", "Lax"),
            }
            for c in cookies
        ]
        with open(outfile, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Exported {len(output)} cookies to {outfile}")
        await browser.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python export_cookies_cdp.py <domain> <outfile.json>")
        sys.exit(1)
    asyncio.run(export_cookies_cdp(sys.argv[1], sys.argv[2]))
