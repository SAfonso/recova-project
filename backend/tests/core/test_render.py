from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.src.core import render

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def cleanup_tmp_artifacts() -> None:
    yield
    for artifact in Path("/tmp").glob("render_test_*.png"):
        artifact.unlink(missing_ok=True)


async def test_capture_screenshot_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    html_file = tmp_path / "minimal.html"
    html_file.write_text("<html><body><div class='slot-1'></div></body></html>", encoding="utf-8")

    output_path = Path("/tmp/render_test_success.png")

    async def fake_screenshot(*, path: str, full_page: bool) -> None:
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n")
        assert full_page is True

    page = SimpleNamespace(
        goto=AsyncMock(),
        add_script_tag=AsyncMock(),
        wait_for_function=AsyncMock(),
        screenshot=AsyncMock(side_effect=fake_screenshot),
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
        html_path=html_file,
        injection_js="window.renderReady = true;",
        output_path=output_path,
    )

    assert ok is True
    assert output_path.exists()


async def test_capture_screenshot_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    html_file = tmp_path / "minimal_timeout.html"
    html_file.write_text("<html><body></body></html>", encoding="utf-8")

    output_path = Path("/tmp/render_test_timeout.png")

    page = SimpleNamespace(
        goto=AsyncMock(),
        add_script_tag=AsyncMock(),
        wait_for_function=AsyncMock(side_effect=TimeoutError("renderReady not set")),
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
        html_path=html_file,
        injection_js="console.log('never ready')",
        output_path=output_path,
    )

    assert ok is False
    assert not output_path.exists()


async def test_no_sandbox_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    html_file = tmp_path / "minimal_flags.html"
    html_file.write_text("<html><body></body></html>", encoding="utf-8")

    output_path = Path("/tmp/render_test_flags.png")

    async def fake_screenshot(*, path: str, full_page: bool) -> None:
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n")

    page = SimpleNamespace(
        goto=AsyncMock(),
        add_script_tag=AsyncMock(),
        wait_for_function=AsyncMock(),
        screenshot=AsyncMock(side_effect=fake_screenshot),
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
        html_path=html_file,
        injection_js="window.renderReady = true;",
        output_path=output_path,
    )

    assert ok is True
    chromium.launch.assert_awaited_once()
    launch_args = chromium.launch.await_args.kwargs.get("args", [])
    assert "--no-sandbox" in launch_args
