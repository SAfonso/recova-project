"""Data-to-DOM binder for lineup slot injection (SDD §13)."""

from __future__ import annotations

import json
import logging
from typing import Any


_MIN_FONT_SIZE_PX = 12
logger = logging.getLogger(__name__)


def _extract_name(slot_data: Any) -> str:
    """Return only the artist name for visual injection."""
    if isinstance(slot_data, dict):
        name = slot_data.get("name", "")
    else:
        name = getattr(slot_data, "get", lambda k, d: "")("name", "")
    return str(name)


def generate_injection_script(lineup: Any, max_slots: int = 8) -> str:
    """Generate a JS snippet that injects lineup names into `.slot-n .name`."""
    if not isinstance(lineup, list):
        logger.error("Invalid lineup payload type: %s", type(lineup).__name__)
        return "window.renderReady = true;"

    lines: list[str] = []

    for slot_index in range(1, max_slots + 1):
        lineup_index = slot_index - 1
        if lineup_index < len(lineup):
            name = _extract_name(lineup[lineup_index])
            safe_name = json.dumps(name, ensure_ascii=False)
            lines.append(
                f"const slotNameEl{slot_index} = document.querySelector('.slot-{slot_index} .name');"
            )
            lines.append(
                f"if (slotNameEl{slot_index}) {{ slotNameEl{slot_index}.textContent = {safe_name}; }}"
            )
        else:
            lines.append(
                f"const slotEl{slot_index} = document.querySelector('.slot-{slot_index}');"
            )
            lines.append(
                f"if (slotEl{slot_index}) {{ slotEl{slot_index}.style.display = 'none'; }}"
            )

    fit_text_iife = f"""
(function () {{
  const nameElements = document.querySelectorAll('.name');
  nameElements.forEach((el) => {{
    const computedStyle = window.getComputedStyle(el);
    let currentFontSize = parseFloat(computedStyle.fontSize);
    let scrollWidth = el.scrollWidth;
    let clientWidth = el.clientWidth;

    while (scrollWidth > clientWidth && currentFontSize > {_MIN_FONT_SIZE_PX}) {{
      currentFontSize -= 1;
      el.style.fontSize = `${{currentFontSize}}px`;
      scrollWidth = el.scrollWidth;
      clientWidth = el.clientWidth;
    }}
  }});
  window.renderReady = true;
}})();
""".strip()

    lines.append(fit_text_iife)
    return "\n".join(lines)


def generate_injection_js(lineup: Any, total_slots: int = 8) -> str:
    """Backward-compatible alias expected by current tests."""
    return generate_injection_script(lineup=lineup, max_slots=total_slots)
