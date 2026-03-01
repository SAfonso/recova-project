"""Playwright screenshot engine agnostic to orchestration layers."""

from __future__ import annotations

from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, async_playwright


async def capture_screenshot(html_path: Path, injection_js: str, output_path: Path) -> bool:
    """Render local HTML + injected JS into a PNG screenshot.

    This function is intentionally agnostic to MCP/n8n orchestration concerns.
    """

    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(html_path.resolve().as_uri())
            await page.add_script_tag(content=injection_js)
            await page.wait_for_function("window.renderReady === true")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(output_path), full_page=True)
            return True
    except Exception:
        return False
    finally:
        if page is not None and not page.is_closed():
            await page.close()
        if context is not None:
            await context.close()
        if browser is not None:
            await browser.close()
