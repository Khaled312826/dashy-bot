import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def export_state():
    # 1. Remove any user-data-dir config so Chrome spins up a brand-new profile
    options = webdriver.ChromeOptions()
    # optional: hide the “controlled by automation” banner
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 2. Launch Chrome (ephemeral profile)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.maximize_window()

    # 3. Go to DoorDash (you’ll hit Cloudflare here)
    driver.get("https://www.doordash.com")
    input("➡️  Solve the Cloudflare check *and* log in in the opened Chrome window, then press ENTER here…")

    # 4. Grab all cookies (httpOnly included!)
    cookies = driver.get_cookies()

    # 5. Build a Playwright‐style state.json
    state = {
        "cookies": cookies,
        "origins": []
    }
    with open("state.json", "w") as f:
        json.dump(state, f, indent=2)

    print(f"✅  Saved {len(cookies)} cookies into state.json")
    driver.quit()

if __name__ == "__main__":
    export_state()
