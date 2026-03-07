"""FormAnalyzer — mapea campos de un Google Form al schema canónico via Gemini.

Recibe la lista de títulos de preguntas y devuelve un dict
{titulo_pregunta → campo_canónico | None}.

Variables de entorno:
    GEMINI_API_KEY
"""

from __future__ import annotations

import json
import os
import re

import google.genai as genai


_CANONICAL_FIELDS = [
    "nombre_artistico",
    "instagram",
    "whatsapp",
    "experiencia",
    "fechas_disponibles",
    "backup",
    "show_proximo",
    "como_nos_conociste",
]

_PROMPT_TEMPLATE = """\
Tienes un formulario de solicitud para actuar en un open mic de comedia.
Las preguntas del formulario son:

{preguntas}

El schema canónico tiene estos campos:
- nombre_artistico: nombre artístico o de escena
- instagram: usuario de Instagram (sin @)
- whatsapp: número de teléfono o WhatsApp
- experiencia: nivel de experiencia en stand-up o comedy
- fechas_disponibles: fechas o días disponibles para actuar
- backup: disponibilidad para cubrir a última hora / sustituto
- show_proximo: show próximo, espectáculo, actuación destacada
- como_nos_conociste: cómo conoció el open mic / canal de captación

Devuelve un JSON válido con este formato exacto:
{{
  "field_mapping": {{
    "<título exacto de la pregunta>": "<campo_canónico>" | null,
    ...
  }}
}}

Reglas:
- Usa el título exacto de la pregunta como clave.
- Si una pregunta encaja claramente en un campo canónico, usa ese campo.
- Si no encaja en ningún campo canónico, usa null.
- No inventes campos canónicos nuevos.
- Responde solo con el JSON, sin explicaciones.
"""


class FormAnalyzer:

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY") or ""

    def analyze(self, form_questions: list[str]) -> dict[str, str | None]:
        """
        Llama a Gemini con los títulos de preguntas del form.
        Devuelve {titulo_pregunta → campo_canónico | None}.
        Lanza ValueError si Gemini devuelve JSON inválido.
        """
        preguntas = "\n".join(f"{i+1}. {q}" for i, q in enumerate(form_questions))
        prompt = _PROMPT_TEMPLATE.format(preguntas=preguntas)

        client = genai.Client(api_key=self._api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw = response.text

        # Strip markdown fences si Gemini los incluye
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())

        try:
            parsed = json.loads(raw)
            return parsed["field_mapping"]
        except (json.JSONDecodeError, KeyError) as exc:
            raise ValueError(f"Gemini devolvió JSON inválido: {raw}") from exc
