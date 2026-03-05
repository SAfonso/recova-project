"""GoogleFormBuilder — crea un Google Form con campos estándar para un open mic.

Usa OAuth2 con refresh token (cuenta del usuario).
Tras crear el form, vincula la Sheet de respuestas e inyecta la columna
open_mic_id con ARRAYFORMULA para que el workflow n8n la lea automáticamente.

Dependencias:
    google-api-python-client>=2.100.0
    google-auth>=2.23.0
    google-auth-oauthlib>=1.0.0

Variables de entorno:
    GOOGLE_OAUTH_CLIENT_ID
    GOOGLE_OAUTH_CLIENT_SECRET
    GOOGLE_OAUTH_REFRESH_TOKEN
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
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

    def __init__(self) -> None:
        client_id     = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
        client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
        refresh_token = os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN", "")

        if not all([client_id, client_secret, refresh_token]):
            raise ValueError(
                "Faltan variables de entorno: GOOGLE_OAUTH_CLIENT_ID, "
                "GOOGLE_OAUTH_CLIENT_SECRET, GOOGLE_OAUTH_REFRESH_TOKEN"
            )

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        creds.refresh(Request())

        self._forms = build("forms", "v1", credentials=creds, cache_discovery=False)
        self._sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
        self._drive  = build("drive",  "v3", credentials=creds, cache_discovery=False)

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
        sheet_id = self._get_linked_sheet_id(form_id, nombre)
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

    def _get_linked_sheet_id(self, form_id: str, nombre: str) -> str:
        """
        Devuelve el linkedSheetId del form si existe.
        Si no existe (Forms API no lo crea automáticamente vía API),
        crea una Spreadsheet propia con las cabeceras correctas.
        """
        form = self._forms.forms().get(formId=form_id).execute()
        linked = form.get("linkedSheetId")
        if linked:
            return linked

        # La Forms API no crea el linked sheet automáticamente vía API.
        # Creamos nuestra propia hoja con cabeceras que coinciden con los campos.
        headers = [
            "Marca temporal",
            "Nombre artístico",
            "Instagram (sin @)",
            "WhatsApp",
            "¿Cuántas veces has actuado en un open mic?",
            "¿Qué fechas te vienen bien?",
            "¿Estarías disponible si nos falla alguien de última hora?",
            "¿Tienes algún show próximo que quieras mencionar?",
            "¿Cómo nos conociste?",
        ]
        spreadsheet = self._sheets.spreadsheets().create(body={
            "properties": {"title": f"Respuestas — {nombre}"},
            "sheets": [{"properties": {"title": "Respuestas"}}],
        }).execute()
        sheet_id = spreadsheet["spreadsheetId"]

        self._sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="Respuestas!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()

        return sheet_id

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
            range=f"{sheet_name}!J1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
