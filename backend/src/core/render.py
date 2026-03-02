"""Playwright screenshot engine agnostic to orchestration layers."""

from __future__ import annotations

from pathlib import Path

from playwright.async_api import async_playwright


async def capture_screenshot(html_path: Path, injection_js: str, output_path: Path) -> bool:
    """Render local HTML + injected JS into a PNG screenshot.

    This function is intentionally agnostic to MCP/n8n orchestration concerns.
    """

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            context = await browser.new_context(viewport={"width": 1080, "height": 1350})
            page = await context.new_page()

            await page.goto(html_path.resolve().as_uri())
            await page.add_script_tag(content=injection_js)
            await page.wait_for_function("window.renderReady === true")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(output_path), full_page=True)
    except Exception as exc:
        print(f"Error en render engine: {exc}")
        return False
    return True
