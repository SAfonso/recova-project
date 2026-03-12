"""CustomScoringProposer — propone reglas de scoring desde campos no canónicos.

Usa Gemini para analizar campos no mapeados al schema canónico y sugerir
reglas de puntuación para el pipeline de scoring custom (Sprint 10, v0.15.0).
"""

from __future__ import annotations

import json
import re

import os

import google.genai as genai

_MODEL = "gemini-2.5-flash"

_PROMPT_TEMPLATE = """\
Tienes un formulario de inscripción para un open mic de comedia.
Los siguientes campos del formulario NO pertenecen al schema canónico
y sus respuestas se guardan como texto libre:

{fields_list}

Para cada campo, propón una regla de scoring que tenga sentido para
seleccionar el lineup de un open mic de comedia. Una regla indica:
qué valor de respuesta da puntos extra (o resta puntos) al cómico.

Devuelve un JSON válido con este formato exacto:
{{
  "rules": [
    {{
      "field": "<nombre exacto del campo>",
      "condition": "equals",
      "value": "<valor que activa la regla>",
      "points": <entero entre -50 y 50>,
      "enabled": true,
      "description": "<descripción breve de la regla en español>"
    }}
  ]
}}

Reglas:
- Usa el nombre exacto del campo como "field".
- "condition" es siempre "equals".
- "value" debe ser un valor razonable que el cómico podría responder.
- "points" positivo = bono, negativo = penalización.
- Si un campo no tiene sentido para scoring, omítelo de la lista.
- Responde solo con el JSON, sin explicaciones ni markdown fences.\
"""


class CustomScoringProposer:
    """Propone reglas de scoring custom usando Gemini."""

    def __init__(self, api_key: str | None = None) -> None:
        resolved_key = api_key or os.environ.get("GEMINI_API_KEY") or ""
        self._client = genai.Client(api_key=resolved_key)

    def propose(self, unmapped_fields: list[str]) -> list[dict]:
        """Propone reglas de scoring para los campos no canónicos dados.

        Args:
            unmapped_fields: lista de títulos de preguntas sin mapeo canónico.

        Returns:
            Lista de dicts con estructura de CustomRule (field, condition,
            value, points, enabled, description).

        Raises:
            ValueError: si Gemini devuelve JSON inválido.
        """
        if not unmapped_fields:
            return []

        fields_list = "\n".join(
            f"{i + 1}. {f}" for i, f in enumerate(unmapped_fields)
        )
        prompt = _PROMPT_TEMPLATE.format(fields_list=fields_list)

        response = self._client.models.generate_content(
            model=_MODEL,
            contents=prompt,
        )
        raw_text = response.text

        # Strip markdown fences si Gemini las incluye
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
        raw_text = re.sub(r"\s*```$", "", raw_text.strip())

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Gemini devolvió JSON inválido: {raw_text}") from exc

        return parsed.get("rules", [])
