"""Debug login page"""
import asyncio
from playwright.async_api import async_playwright

async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 900})

        await page.goto("http://127.0.0.1:8010/login")
        await page.wait_for_timeout(1000)

        # Get all buttons
        buttons = await page.locator("button").all()
        print(f"Found {len(buttons)} buttons:")
        for i, btn in enumerate(buttons):
            text = await btn.inner_text()
            print(f"  [{i}] {text!r}")

        # Take screenshot
        await page.screenshot(path="/Users/jwkj/easyquant/test_results/login-page.png")
        print("Screenshot saved")

        await browser.close()

asyncio.run(debug())
