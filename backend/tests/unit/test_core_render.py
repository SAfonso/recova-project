from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.src.core import render

pytestmark = pytest.mark.asyncio


async def test_capture_screenshot_waits_render_ready_and_uses_root_safe_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    output_path = tmp_path / "lineup.png"

    page = SimpleNamespace(
        goto=AsyncMock(),
        add_script_tag=AsyncMock(),
        wait_for_function=AsyncMock(),
        screenshot=AsyncMock(),
        is_closed=lambda: False,
        close=AsyncMock(),
    )
    context = SimpleNamespace(new_page=AsyncMock(return_value=page), close=AsyncMock())
    browser = SimpleNamespace(new_context=AsyncMock(return_value=context), close=AsyncMock())

    chromium = SimpleNamespace(launch=AsyncMock(return_value=browser))

    class _PlaywrightCM:
        async def __aenter__(self):
            return SimpleNamespace(chromium=chromium)

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(render, "async_playwright", lambda: _PlaywrightCM())

    ok = await render.capture_screenshot(
        html_path=Path("backend/src/templates/catalog/active/template.html"),
        injection_js="window.renderReady = true;",
        output_path=output_path,
    )

    assert ok is True
    chromium.launch.assert_awaited_once_with(args=["--no-sandbox", "--disable-dev-shm-usage"])
    page.wait_for_function.assert_awaited_once_with("window.renderReady === true")
    page.screenshot.assert_awaited_once_with(path=str(output_path), full_page=True)
    page.close.assert_awaited_once()
    context.close.assert_awaited_once()
    browser.close.assert_awaited_once()


async def test_capture_screenshot_closes_browser_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    output_path = tmp_path / "lineup.png"

    page = SimpleNamespace(
        goto=AsyncMock(side_effect=RuntimeError("boom")),
        add_script_tag=AsyncMock(),
        wait_for_function=AsyncMock(),
        screenshot=AsyncMock(),
        is_closed=lambda: False,
        close=AsyncMock(),
    )
    context = SimpleNamespace(new_page=AsyncMock(return_value=page), close=AsyncMock())
    browser = SimpleNamespace(new_context=AsyncMock(return_value=context), close=AsyncMock())

    chromium = SimpleNamespace(launch=AsyncMock(return_value=browser))

    class _PlaywrightCM:
        async def __aenter__(self):
            return SimpleNamespace(chromium=chromium)

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(render, "async_playwright", lambda: _PlaywrightCM())

    ok = await render.capture_screenshot(
        html_path=Path("backend/src/templates/catalog/active/template.html"),
        injection_js="window.renderReady = true;",
        output_path=output_path,
    )

    assert ok is False
    page.close.assert_awaited_once()
    context.close.assert_awaited_once()
    browser.close.assert_awaited_once()
