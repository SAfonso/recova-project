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
        set_viewport_size=AsyncMock(),
        wait_for_function=AsyncMock(),
        wait_for_timeout=AsyncMock(),
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
    sleep_mock = AsyncMock()
    monkeypatch.setattr(render.asyncio, "sleep", sleep_mock)

    ok = await render.capture_screenshot(
        html_path=html_file,
        injection_js="window.renderReady = true;",
        output_path=output_path,
    )

    assert ok is True
    assert output_path.exists()
    page.goto.assert_awaited_once_with(f"file://{html_file}", wait_until="load")
    page.wait_for_function.assert_awaited_once_with("window.renderReady === true")
    page.set_viewport_size.assert_awaited_once_with({"width": 1080, "height": 1350})
    sleep_mock.assert_awaited_once_with(0.5)
    page.screenshot.assert_awaited_once_with(path=str(output_path), full_page=True)
    browser.new_context.assert_awaited_once_with()


async def test_capture_screenshot_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    html_file = tmp_path / "minimal_timeout.html"
    html_file.write_text("<html><body></body></html>", encoding="utf-8")

    output_path = Path("/tmp/render_test_timeout.png")

    page = SimpleNamespace(
        goto=AsyncMock(),
        add_script_tag=AsyncMock(),
        set_viewport_size=AsyncMock(),
        wait_for_function=AsyncMock(side_effect=TimeoutError("renderReady not set")),
        wait_for_timeout=AsyncMock(),
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
    sleep_mock = AsyncMock()
    monkeypatch.setattr(render.asyncio, "sleep", sleep_mock)

    ok = await render.capture_screenshot(
        html_path=html_file,
        injection_js="console.log('never ready')",
        output_path=output_path,
    )

    assert ok is False
    page.goto.assert_awaited_once_with(f"file://{html_file}", wait_until="load")
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
        set_viewport_size=AsyncMock(),
        wait_for_function=AsyncMock(),
        wait_for_timeout=AsyncMock(),
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
    sleep_mock = AsyncMock()
    monkeypatch.setattr(render.asyncio, "sleep", sleep_mock)

    ok = await render.capture_screenshot(
        html_path=html_file,
        injection_js="window.renderReady = true;",
        output_path=output_path,
    )

    assert ok is True
    page.set_viewport_size.assert_awaited_once_with({"width": 1080, "height": 1350})
    sleep_mock.assert_awaited_once_with(0.5)
    chromium.launch.assert_awaited_once()
    launch_args = chromium.launch.await_args.kwargs.get("args", [])
    assert "--no-sandbox" in launch_args
    assert "--disable-dev-shm-usage" in launch_args
    assert "--disable-gpu" in launch_args


async def test_capture_screenshot_returns_false_and_logs_error_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    html_file = tmp_path / "minimal_fail.html"
    html_file.write_text("<html><body></body></html>", encoding="utf-8")
    output_path = Path("/tmp/render_test_failure.png")

    page = SimpleNamespace(
        goto=AsyncMock(side_effect=RuntimeError("boom")),
        add_script_tag=AsyncMock(),
        set_viewport_size=AsyncMock(),
        wait_for_function=AsyncMock(),
        wait_for_timeout=AsyncMock(),
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
    sleep_mock = AsyncMock()
    monkeypatch.setattr(render.asyncio, "sleep", sleep_mock)

    ok = await render.capture_screenshot(
        html_path=html_file,
        injection_js="window.renderReady = true;",
        output_path=output_path,
    )

    assert ok is False
    page.goto.assert_awaited_once_with(f"file://{html_file}", wait_until="load")
    output = capsys.readouterr().out
    assert "Error en render engine:" in output
    assert "boom" in output
