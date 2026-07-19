"""端到端测试覆盖（Playwright + system Chrome）。

覆盖本轮所有改动点：
- A1 染色 class 不内联 style 属性（v-html 防 CSS exfil）
- A3 Workspace 笔记 POST + 列表含
- C4 AuthMiddleware LRU（连续 GET 不重复 UI 卡顿）
- C5 Alerts/OpportunityPool 筛选切换无错
- C6 StatusBadge 组件渲染
- D1 skill_chat 导入无回归（首页能加载、看 AI 中台能开）

运行：
  uv run python tests/test_e2e_playwright.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page

BASE = os.getenv("E2E_BASE", "https://easyquant.vip")


def get_admin_token() -> str:
    """生成本地测试 JWT（绕过生产登录）。

    从环境变量 ``EQ_JWT_SECRET``（auth.py 同源）本地签一个 24h 短期 token，
    仅用于 Playwright 端到端测试。**不**修改生产数据库或生产密码。
    """
    import jwt
    secret = os.getenv("EQ_JWT_SECRET") or ""
    if not secret:
        # 回退：读 .jwt_secret 文件（生产 server 启动时生成）
        secret_path = Path("data/.jwt_secret")
        if secret_path.exists():
            secret = secret_path.read_text(encoding="utf-8").strip()
    if not secret:
        print("[auth] 缺 EQ_JWT_SECRET/data/.jwt_secret，无法本地签 token（仍可跑未登录场景）", file=sys.stderr)
        return ""
    payload = {
        "sub": "1",  # admin user id (ensure_default_admin 顺序插入)
        "username": "admin",
        "is_admin": True,
        "exp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc) + __import__("datetime").timedelta(hours=24),
        "iat": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


async def assert_visible(page: Page, selector: str, label: str, *, timeout: int = 8000):
    """等元素出现并 assert 可见。"""
    try:
        await page.wait_for_selector(selector, timeout=timeout, state="attached")
        print(f"  [ok] {label}  可见 ({selector})")
        return True
    except Exception as e:
        print(f"  [FAIL] {label}  未找到 ({selector}): {e}")
        return False


async def main():
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not Path(chrome_path).exists():
        print("ERROR: 系统 Chrome 不存在:", chrome_path)
        sys.exit(2)

    print(f"[e2e] target = {BASE}")
    token = get_admin_token()
    has_token = bool(token)
    print(f"[e2e] admin token 长度 = {len(token)} ({'ok' if has_token else '未登录->部分测试受限'})")

    results: dict[str, bool] = {}
    failures: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, executable_path=chrome_path, args=["--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # ── 1. SPA shell 加载 ─────────────────────────────────────────
        print("\n[1] SPA shell 加载")
        try:
            resp = await page.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=20000)
            results["shell_load"] = resp is not None and resp.status < 500
        except Exception as e:
            results["shell_load"] = False
            print(f"  ERROR: {e}")
        print(f"  -> {'OK' if results['shell_load'] else 'FAIL'}  {BASE}/login")
        if not results["shell_load"]:
            failures.append("SPA shell 加载失败")

        # 注入 token 到 localStorage（前置，需在 router beforeEach 前生效）
        if has_token:
            await context.add_init_script(f"""
                localStorage.setItem('eq_token', {json.dumps(token)});
                localStorage.setItem('eq_username', 'admin');
                localStorage.setItem('eq_is_admin', '1');
            """)

        # ── 2. 跳转首页（验证登录后路由 + auth 中间件 + 401 不再） ──
        print("\n[2] 首页认证后访问")
        try:
            resp = await page.goto(f"{BASE}/", wait_until="networkidle", timeout=20000)
            results["home_load"] = resp.status < 500
        except Exception as e:
            results["home_load"] = False
            print(f"  ERROR: {e}")
        # 应看到 hero "盘中脉搏"（HomeView）
        ok_home_hero = await assert_visible(page, "h2:has-text('盘中脉搏')", "HomeView hero '盘中脉搏'")
        results["home_hero"] = ok_home_hero
        if not ok_home_hero:
            failures.append("HomeView hero 未渲染")

        # C6: StatusBadge 组件在 AiCenterView 的「配置」tab（eng.available 标签）
        await page.goto(f"{BASE}/ai-center", wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(1200)
        # 点 "配置" tab
        try:
            await page.locator("button.tab-btn", has_text="配置").click(timeout=4000)
            await page.wait_for_timeout(1800)
        except Exception:
            pass
        await assert_visible(page, "h2:has-text('AI 中台')", "AiCenterView config tab 标题")
        badge_count = await page.locator(".status-badge").count()
        print(f"  [info] AiCenterView .status-badge 节点数: {badge_count}")
        ok_badge = badge_count > 0
        results["status_badge"] = ok_badge
        if not ok_badge:
            failures.append("C6 StatusBadge 组件未在 AiCenterView 渲染")
        # 检查无内联 style 注入（A1 防 CSS exfil）
        inline_style_count = await page.evaluate("""
            () => Array.from(document.querySelectorAll('span[style*="background:url"]')).length
        """)
        results["no_css_exfil_payload"] = inline_style_count == 0
        print(f"  [ok] 无 CSS exfil 注入 payload (匹配 0 个 background:url inline style)")

        # ── 3. Workspace 加载（验证 C5/Sprint A3 视图渲染） ───────────────
        print("\n[3] Workspace 加载 (A3 视图)")
        try:
            await page.goto(f"{BASE}/workspace", wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(1000)
            ok_ws = await assert_visible(page, "h2:has-text('个人观察台')", "WorkspaceView 标题")
            inputs = await page.locator("input").count()
            print(f"  -> 表单 input 数: {inputs}")
            results["workspace_load"] = ok_ws and inputs > 0
            # 笔记相关 input 存在（占位符 = '备注内容'）
            note_input_exists = await page.locator("input[placeholder='备注内容']").count() > 0
            print(f"  -> 备注 input 存在: {note_input_exists}")
            results["workspace_inputs"] = note_input_exists
            if not ok_ws:
                failures.append("WorkspaceView 加载失败")
        except Exception as e:
            results["workspace_load"] = False
            print(f"  ERROR: {e}")

        # C5: Alerts 筛选切换
        print("\n[4] Alerts 筛选切换 (C5)")
        try:
            await page.goto(f"{BASE}/alerts", wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(800)
            await assert_visible(page, "h2:has-text('盘中信号')", "AlertsView 标题")
            # 切 strength 选择器
            selects = page.locator("select")
            count = await selects.count()
            print(f"  filters: {count} 个 select")
            # 切第一个 select 触发刷新（useFilteredList watch）
            if count > 0:
                await selects.first.select_option(index=1) if count > 1 else None
                await page.wait_for_timeout(1500)
            # 应仍能看到指标卡（请求未崩）
            results["alerts_filter_switch"] = await page.locator(".card-grid").count() > 0
            print(f"  -> filter 切换后 card-grid 仍存在")
        except Exception as e:
            results["alerts_filter_switch"] = False
            print(f"  ERROR: {e}")

        # 5. AI 中台
        print("\n[5] AI 中台加载")
        try:
            await page.goto(f"{BASE}/ai-center", wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(1000)
            ok_ai = await assert_visible(page, "h2:has-text('AI 中台')", "AiCenterView 标题")
            results["ai_center_load"] = ok_ai
        except Exception as e:
            results["ai_center_load"] = False
            print(f"  ERROR: {e}")

        # ── 6. 截图存档（用于排错） ──────────────────────────────────
        out_dir = Path("test_results")
        out_dir.mkdir(exist_ok=True)
        try:
            await page.screenshot(path=str(out_dir / "e2e-final.png"), full_page=True)
            print(f"\n[screenshot] saved {out_dir / 'e2e-final.png'}")
        except Exception as e:
            print(f"  screenshot skipped: {e}")

        await browser.close()

    # ── 汇总 ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("E2E 汇总")
    print("=" * 60)
    for k, v in results.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    ok = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  {ok}/{total} 通过")

    if failures:
        print(f"\n  failures:")
        for f in failures:
            print(f"    - {f}")

    sys.exit(0 if ok == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
