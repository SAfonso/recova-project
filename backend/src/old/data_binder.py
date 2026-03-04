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


def _extract_event_date(lineup: list[Any]) -> str:
    """Best-effort extraction of event date from lineup payload."""
    for slot_data in lineup:
        if not isinstance(slot_data, dict):
            continue
        for key in ("event_date", "fecha_evento", "eventDate", "date"):
            raw_value = slot_data.get(key)
            if isinstance(raw_value, str) and raw_value.strip():
                return raw_value.strip()
    return ""


def generate_injection_script(lineup: Any, max_slots: int = 8) -> str:
    """Generate a JS snippet that injects lineup names into `.slot-n .name`."""
    if not isinstance(lineup, list):
        logger.error("Invalid lineup payload type: %s", type(lineup).__name__)
        return "window.renderReady = true;"

    lines: list[str] = []
    lineup_names = [_extract_name(slot_data) for slot_data in lineup[:max_slots]]
    safe_lineup_names = json.dumps(lineup_names, ensure_ascii=False)
    safe_event_date = json.dumps(_extract_event_date(lineup), ensure_ascii=False)

    lines.append(f"const recovaLineupNames = {safe_lineup_names};")
    lines.append(f"const recovaEventDate = {safe_event_date};")

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
  const hasPlaceholderTokens = (text) =>
    typeof text === 'string' && (text.includes('{{{{') || text.includes('{{%'));

  const firstLineupName = (recovaLineupNames.find((name) => String(name || '').trim().length > 0) || '').trim();
  const resolvedEventDate = String(recovaEventDate || '').trim() || new Date().toISOString().slice(0, 10);

  const lineupContainer = document.querySelector('.lineup');
  if (lineupContainer) {{
    const existingComicTemplate = lineupContainer.querySelector('.comico');
    const cleanNames = recovaLineupNames
      .map((name) => String(name || '').trim())
      .filter((name) => name.length > 0);

    if (cleanNames.length > 0) {{
      lineupContainer.innerHTML = '';
      cleanNames.forEach((name) => {{
        const comicEl = existingComicTemplate
          ? existingComicTemplate.cloneNode(false)
          : document.createElement('div');
        if (!comicEl.className) {{
          comicEl.className = 'comico';
        }}
        comicEl.textContent = name;
        lineupContainer.appendChild(comicEl);
      }});
    }}
  }}

  const eventDateTargets = document.querySelectorAll('.footer, .event-date, [data-event-date]');
  eventDateTargets.forEach((target) => {{
    if (target && hasPlaceholderTokens(target.textContent || '')) {{
      target.textContent = resolvedEventDate;
    }}
  }});

  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  while (walker.nextNode()) {{
    textNodes.push(walker.currentNode);
  }}

  textNodes.forEach((node) => {{
    const originalText = node.nodeValue || '';
    if (!hasPlaceholderTokens(originalText)) {{
      return;
    }}

    const nextText = originalText
      .replace(/\\{{\\{{\\s*(comico|comic)\\.name\\s*\\}}\\}}/gi, firstLineupName)
      .replace(/\\{{\\{{\\s*event\\.date\\s*\\}}\\}}/gi, resolvedEventDate)
      .replace(/\\{{%\\s*for[^%]*%\\}}/gi, '')
      .replace(/\\{{%\\s*endfor\\s*%\\}}/gi, '')
      .replace(/\\{{\\{{\\s*[^}}]+\\s*\\}}\\}}/g, '')
      .trim();

    if (nextText !== originalText) {{
      node.nodeValue = nextText;
    }}
  }});

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

  const comicElements = document.querySelectorAll('.comico');
  comicElements.forEach((el) => {{
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
