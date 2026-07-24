"""Screenshot AI center result page - set token and reload"""
import asyncio
from playwright.async_api import async_playwright

async def screenshot_ai_center():
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # Desktop view
        desktop_context = await browser.new_context(viewport={"width": 1280, "height": 900})
        desktop_page = await desktop_context.new_page()

        # Get token via API
        import requests
        resp = requests.post("http://127.0.0.1:8010/api/auth/login", json={"username": "admin", "password": "admin123"})
        token = resp.json()["access_token"]

        # Go to login, set token, reload to let Vue pick it up
        await desktop_page.goto("http://127.0.0.1:8010/login")
        await desktop_page.evaluate(f"""() => {{
            localStorage.setItem('eq_token', '{token}');
            localStorage.setItem('eq_username', 'admin');
            localStorage.setItem('eq_is_admin', '1');
        }}""")
        # Reload so Vue router guard sees the token
        await desktop_page.reload()
        await desktop_page.wait_for_timeout(2000)

        # Now navigate to AI center
        await desktop_page.goto("http://127.0.0.1:8010/ai-center")
        await desktop_page.wait_for_load_state("networkidle")
        await desktop_page.wait_for_timeout(2000)

        url = desktop_page.url
        print(f"Current URL: {url}")

        # If still on login, something is wrong
        if "login" in url:
            print("Still on login page after setting token")
            await desktop_page.screenshot(path="/Users/jwkj/easyquant/test_results/ai-login-debug.png")
            await browser.close()
            return

        # Find and click "任务结果" tab
        tabs = await desktop_page.locator(".tab-btn").all()
        print(f"Found {len(tabs)} tabs")
        if len(tabs) > 2:
            await tabs[2].click()
            await desktop_page.wait_for_timeout(1000)

        # Fill date
        await desktop_page.locator("input[type='date']").fill("2026-06-09")
        await desktop_page.wait_for_timeout(1000)

        # Select first job
        select = desktop_page.locator("select.job-select")
        options = await select.locator("option").count()
        print(f"Found {options} options")

        if options > 1:
            await select.select_option(index=1)
            await desktop_page.wait_for_timeout(2000)

        await desktop_page.screenshot(path="/Users/jwkj/easyquant/test_results/ai-result-desktop.png", full_page=True)
        print("Desktop screenshot saved")

        # Mobile view
        iphone = p.devices["iPhone 14"]
        mobile_context = await browser.new_context(**iphone)
        mobile_page = await mobile_context.new_page()

        await mobile_page.goto("http://127.0.0.1:8010/login")
        await mobile_page.evaluate(f"""() => {{
            localStorage.setItem('eq_token', '{token}');
            localStorage.setItem('eq_username', 'admin');
            localStorage.setItem('eq_is_admin', '1');
        }}""")
        await mobile_page.reload()
        await mobile_page.wait_for_timeout(2000)

        await mobile_page.goto("http://127.0.0.1:8010/ai-center")
        await mobile_page.wait_for_load_state("networkidle")
        await mobile_page.wait_for_timeout(2000)

        mobile_tabs = await mobile_page.locator(".tab-btn").all()
        if len(mobile_tabs) > 2:
            await mobile_tabs[2].click()
            await mobile_page.wait_for_timeout(1000)

        await mobile_page.locator("input[type='date']").fill("2026-06-09")
        await mobile_page.wait_for_timeout(1000)

        if options > 1:
            await mobile_page.locator("select.job-select").select_option(index=1)
            await mobile_page.wait_for_timeout(2000)

        await mobile_page.screenshot(path="/Users/jwkj/easyquant/test_results/ai-result-mobile.png", full_page=True)
        print("Mobile screenshot saved")

        await browser.close()

asyncio.run(screenshot_ai_center())
