"""Debug AI center page structure"""
import asyncio
from playwright.async_api import async_playwright

async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        # Login
        import requests
        resp = requests.post("http://127.0.0.1:8010/api/auth/login", json={"username": "admin", "password": "admin123"})
        token = resp.json()["access_token"]

        await page.goto("http://127.0.0.1:8010/login")
        await page.evaluate(f"""() => {{
            localStorage.setItem('eq_token', '{token}');
            localStorage.setItem('eq_username', 'admin');
            localStorage.setItem('eq_is_admin', '1');
        }}""")
        await page.goto("http://127.0.0.1:8010/ai-center")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # Find tab buttons
        tabs = await page.locator(".tab-btn, .tab-nav button, nav button").all()
        print(f"Found {len(tabs)} tab buttons:")
        for i, tab in enumerate(tabs):
            text = await tab.inner_text()
            print(f"  [{i}] {text!r}")

        # Take screenshot
        await page.screenshot(path="/Users/jwkj/easyquant/test_results/ai-center-debug.png", full_page=True)
        print("Screenshot saved")

        await browser.close()

asyncio.run(debug())
