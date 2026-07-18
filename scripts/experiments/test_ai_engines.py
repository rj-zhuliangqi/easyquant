#!/usr/bin/env python3
"""
Playwright E2E test for AI Center engine config page.
Verifies that all engines show correct availability status.
"""

import asyncio
from playwright.async_api import async_playwright


BASE_URL = "http://127.0.0.1:8010"
USERNAME = "admin"
PASSWORD = "admin123"


async def test_ai_center_engines():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900}
        )
        page = await context.new_page()

        # Step 1: Login
        print("Step 1: Logging in...")
        await page.goto(f"{BASE_URL}/login")
        await page.wait_for_selector('input[type="text"]')
        await asyncio.sleep(1)
        await page.fill('input[type="text"]', USERNAME)
        await page.fill('input[type="password"]', PASSWORD)
        buttons = await page.query_selector_all('button')
        if buttons:
            await buttons[0].click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(1)

        current_url = page.url
        if "/login" in current_url:
            print("   ❌ Login failed - still on login page")
            await browser.close()
            return False
        print("   ✅ Login successful")

        # Step 2: Navigate to AI Center
        print("\nStep 2: Navigating to AI Center...")
        await page.goto(f"{BASE_URL}/ai-center")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        await page.screenshot(path="/Users/jwkj/easyquant/test_results/01-ai-center-overview.png")
        print("   Screenshot saved: 01-ai-center-overview.png")

        # Step 3: Click on "配置" tab
        print("\nStep 3: Clicking config tab...")
        config_tab = None
        for selector in ['button:has-text("配置")', 'button:has-text("🔧")', '.tab-btn:has-text("配置")']:
            config_tab = await page.query_selector(selector)
            if config_tab:
                break

        if not config_tab:
            all_buttons = await page.query_selector_all('button')
            for btn in all_buttons:
                text = await btn.inner_text()
                if "🔧" in text or "配置" in text:
                    config_tab = btn
                    break

        if config_tab:
            await config_tab.click()
            await asyncio.sleep(2)
            await page.screenshot(path="/Users/jwkj/easyquant/test_results/02-ai-center-config.png")
            print("   Screenshot saved: 02-ai-center-config.png")
        else:
            print("   ❌ Could not find config tab")
            await browser.close()
            return False

        # Step 4: Verify engine cards
        print("\nStep 4: Checking Engine Cards ---")

        cards = await page.query_selector_all('.engine-card')
        print(f"   Found {len(cards)} engine cards")

        results = {}

        for i, card in enumerate(cards):
            card_text = await card.inner_text()
            card_html = await card.evaluate("el => el.outerHTML")
            is_disabled = "disabled" in card_html.lower()
            has_success = "status-success" in card_html
            has_danger = "status-danger" in card_html

            if "Claude Code CLI" in card_text:
                print(f"   Card {i}: Claude Code CLI")
                print(f"      - disabled class: {is_disabled}")
                print(f"      - status-success: {has_success}")
                print(f"      - status-danger: {has_danger}")
                results["claude"] = {
                    "name": "Claude Code CLI",
                    "available": has_success and not is_disabled,
                    "disabled": is_disabled,
                    "success": has_success,
                    "danger": has_danger,
                }
                status = "✅ PASS" if results["claude"]["available"] else "❌ FAIL"
                print(f"      - {status}")

            elif "Goose CLI" in card_text:
                print(f"   Card {i}: Goose CLI")
                print(f"      - disabled class: {is_disabled}")
                print(f"      - status-success: {has_success}")
                print(f"      - status-danger: {has_danger}")
                results["goose"] = {
                    "name": "Goose CLI",
                    "available": has_success and not is_disabled,
                    "disabled": is_disabled,
                    "success": has_success,
                    "danger": has_danger,
                }
                status = "✅ PASS" if results["goose"]["available"] else "❌ FAIL"
                print(f"      - {status}")

            elif "Custom Script" in card_text:
                print(f"   Card {i}: Custom Script")
                print(f"      - disabled class: {is_disabled}")
                print(f"      - status-success: {has_success}")
                print(f"      - status-danger: {has_danger}")
                results["custom"] = {
                    "name": "Custom Script",
                    "available": has_success and not is_disabled,
                    "disabled": is_disabled,
                    "success": has_success,
                    "danger": has_danger,
                }
                status = "✅ PASS" if results["custom"]["available"] else "❌ FAIL"
                print(f"      - {status}")

        # Final screenshot
        await page.screenshot(path="/Users/jwkj/easyquant/test_results/03-ai-center-final.png", full_page=True)
        print("\n   Screenshot saved: 03-ai-center-final.png")

        await browser.close()

        # Summary
        print("\n" + "=" * 50)
        print("TEST RESULTS SUMMARY")
        print("=" * 50)
        all_pass = True
        for key, result in results.items():
            status = "✅ AVAILABLE (PASS)" if result["available"] else "❌ UNAVAILABLE (FAIL)"
            if not result["available"]:
                all_pass = False
            print(f"{result['name']}: {status}")
        print(f"\nOverall: {'✅ ALL TESTS PASSED' if all_pass else '❌ SOME TESTS FAILED'}")
        print("=" * 50)

        return all_pass


if __name__ == "__main__":
    import os
    os.makedirs("/Users/jwkj/easyquant/test_results", exist_ok=True)
    result = asyncio.run(test_ai_center_engines())
    exit(0 if result else 1)
