"""GoogleFormBuilder — crea un Google Form con campos estándar para un open mic.

Usa una service account del sistema (sin OAuth por usuario).
Tras crear el form, vincula la Sheet de respuestas e inyecta la columna
open_mic_id con ARRAYFORMULA para que el workflow n8n la lea automáticamente.

Dependencias:
    google-api-python-client>=2.100.0
    google-auth>=2.23.0

Variables de entorno:
    GOOGLE_SA_CREDENTIALS_PATH — ruta al JSON de la service account
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from google.oauth2 import service_account
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ---------------------------------------------------------------------------
# Definición de los 8 campos del form (contrato con ingesta)
# Orden y nombres deben coincidir con google_form_campos_spec.md §2
# ---------------------------------------------------------------------------

_FORM_QUESTIONS = [
    {
        "title": "Nombre artístico",
        "required": True,
        "kind": "textQuestion",
        "paragraph": False,
    },
    {
        "title": "Instagram (sin @)",
        "required": True,
        "kind": "textQuestion",
        "paragraph": False,
    },
    {
        "title": "WhatsApp",
        "required": True,
        "kind": "textQuestion",
        "paragraph": False,
    },
    {
        "title": "¿Cuántas veces has actuado en un open mic?",
        "required": True,
        "kind": "choiceQuestion",
        "options": [
            "Es mi primera vez",
            "He probado alguna vez",
            "Llevo tiempo haciendo stand-up",
            "Soy un profesional / tengo cachés",
        ],
    },
    {
        "title": "¿Qué fechas te vienen bien?",
        "required": True,
        "kind": "textQuestion",
        "paragraph": False,
    },
    {
        "title": "¿Estarías disponible si nos falla alguien de última hora?",
        "required": True,
        "kind": "choiceQuestion",
        "options": ["Sí", "No"],
    },
    {
        "title": "¿Tienes algún show próximo que quieras mencionar?",
        "required": False,
        "kind": "textQuestion",
        "paragraph": True,
    },
    {
        "title": "¿Cómo nos conociste?",
        "required": False,
        "kind": "textQuestion",
        "paragraph": False,
    },
]


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class FormCreationResult:
    form_id: str
    form_url: str
    sheet_id: str
    sheet_url: str


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class GoogleFormBuilder:
    """Crea Google Forms con campos estándar usando una service account."""

    def __init__(self, credentials_path: str | None = None) -> None:
        path = credentials_path or os.environ.get("GOOGLE_SA_CREDENTIALS_PATH")
        if not path:
            raise ValueError(
                "GOOGLE_SA_CREDENTIALS_PATH no definido y no se pasó credentials_path."
            )

        creds = service_account.Credentials.from_service_account_file(
            path, scopes=SCOPES
        )
        self._forms = build("forms", "v1", credentials=creds, cache_discovery=False)
        self._sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

    # ------------------------------------------------------------------

    def create_form_for_open_mic(
        self,
        open_mic_id: str,
        nombre: str,
    ) -> FormCreationResult:
        """
        1. Crea el Google Form con los 8 campos estándar.
        2. Activa la recogida de respuestas en Sheet.
        3. Inyecta columna open_mic_id con ARRAYFORMULA en la Sheet.
        4. Devuelve FormCreationResult con URLs y IDs.
        """
        form_id = self._create_form(nombre)
        self._add_questions(form_id)
        sheet_id = self._get_linked_sheet_id(form_id)
        self._inject_open_mic_id_column(sheet_id, open_mic_id)

        form_url = f"https://docs.google.com/forms/d/{form_id}/viewform"
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"

        return FormCreationResult(
            form_id=form_id,
            form_url=form_url,
            sheet_id=sheet_id,
            sheet_url=sheet_url,
        )

    # ------------------------------------------------------------------
    # Pasos internos
    # ------------------------------------------------------------------

    def _create_form(self, nombre: str) -> str:
        """Crea el form vacío y devuelve su form_id."""
        body = {"info": {"title": f"Solicitudes — {nombre}"}}
        result = self._forms.forms().create(body=body).execute()
        return result["formId"]

    def _add_questions(self, form_id: str) -> None:
        """Añade los 8 campos via batchUpdate."""
        requests = []
        for index, q in enumerate(_FORM_QUESTIONS):
            item = self._build_item(q)
            requests.append({
                "createItem": {
                    "item": item,
                    "location": {"index": index},
                }
            })

        self._forms.forms().batchUpdate(
            formId=form_id,
            body={"requests": requests},
        ).execute()

    def _build_item(self, q: dict) -> dict:
        """Convierte la definición de pregunta al formato de la Forms API."""
        item: dict = {"title": q["title"]}

        if q["kind"] == "textQuestion":
            item["questionItem"] = {
                "question": {
                    "required": q["required"],
                    "textQuestion": {"paragraph": q["paragraph"]},
                }
            }
        elif q["kind"] == "choiceQuestion":
            item["questionItem"] = {
                "question": {
                    "required": q["required"],
                    "choiceQuestion": {
                        "type": "RADIO",
                        "options": [{"value": opt} for opt in q["options"]],
                    },
                }
            }

        return item

    def _get_linked_sheet_id(self, form_id: str) -> str:
        """
        Google Forms crea automáticamente una Sheet al activar respuestas.
        La Sheet se crea al llamar a la API de Forms — leemos su ID del form.
        Si aún no existe, la creamos explícitamente via batchUpdate.
        """
        form = self._forms.forms().get(formId=form_id).execute()
        linked = form.get("linkedSheetId")
        if linked:
            return linked

        # Forzar creación de Sheet vinculada
        self._forms.forms().batchUpdate(
            formId=form_id,
            body={"requests": [{"createItem": {}}]},
        )
        # Re-leer
        form = self._forms.forms().get(formId=form_id).execute()
        linked = form.get("linkedSheetId")
        if not linked:
            raise RuntimeError(
                f"No se pudo obtener linkedSheetId para form {form_id}. "
                "Activa manualmente 'Vincular a Sheets' en Google Forms."
            )
        return linked

    def _inject_open_mic_id_column(self, sheet_id: str, open_mic_id: str) -> None:
        """
        Escribe la cabecera 'open_mic_id' en la primera celda libre (col I = col 9)
        y la ARRAYFORMULA en la fila 2 para que se auto-rellene en cada respuesta.
        """
        spreadsheet = (
            self._sheets.spreadsheets()
            .get(spreadsheetId=sheet_id)
            .execute()
        )
        sheet_name = spreadsheet["sheets"][0]["properties"]["title"]

        values = [
            ["open_mic_id"],
            [f'=ARRAYFORMULA(IF(B2:B<>"","{open_mic_id}",""))'],
        ]

        self._sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{sheet_name}!I1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
