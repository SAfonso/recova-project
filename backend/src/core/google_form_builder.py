"""GoogleFormBuilder — crea un Google Form con campos estándar para un open mic.

Usa OAuth2 con refresh token (cuenta del usuario).
Tras crear el form:
  1. Vincula la Sheet de respuestas e inyecta columna open_mic_id (legado).
  2. Despliega un Apps Script bound al form con trigger onFormSubmit que hace
     POST al backend con los datos de la respuesta + open_mic_id.

Dependencias:
    google-api-python-client>=2.100.0
    google-auth>=2.23.0
    google-auth-oauthlib>=1.0.0

Variables de entorno:
    GOOGLE_OAUTH_CLIENT_ID
    GOOGLE_OAUTH_CLIENT_SECRET
    GOOGLE_OAUTH_REFRESH_TOKEN
    BACKEND_URL  (ej: https://api.machango.org)
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
import os
import random
from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


# ---------------------------------------------------------------------------
# Paleta de colores para el form (Sprint 13)
# ---------------------------------------------------------------------------

_FORM_BG_PALETTE = [
    "#F28B82", "#FBBC04", "#FFF475", "#CCFF90",
    "#A8DAB5", "#CBF0F8", "#AECBFA", "#D7AEFB",
    "#FDCFE8", "#E6C9A8", "#E8EAED", "#FF8A65",
]

_DIA_SEMANA_MAP = {
    "Lunes": 0, "Martes": 1, "Miércoles": 2, "Miercoles": 2,
    "Jueves": 3, "Viernes": 4, "Sábado": 5, "Sabado": 5, "Domingo": 6,
}

SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ---------------------------------------------------------------------------
# Plantilla Apps Script para el trigger onFormSubmit
# Bake-in de open_mic_id y backend_url para evitar dependencia de ScriptProperties
# ---------------------------------------------------------------------------

_APPS_SCRIPT_TEMPLATE = """\
var OPEN_MIC_ID = "{open_mic_id}";
var BACKEND_URL = "{backend_url}";
var API_KEY = "{api_key}";

function onFormSubmitHandler(e) {{
  var itemResponses = e.response.getItemResponses();
  var payload = {{ open_mic_id: OPEN_MIC_ID }};
  itemResponses.forEach(function(r) {{
    payload[r.getItem().getTitle()] = r.getResponse();
  }});
  UrlFetchApp.fetch(BACKEND_URL, {{
    method: "post",
    contentType: "application/json",
    headers: {{ "X-API-Key": API_KEY }},
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  }});
}}

function setup() {{
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {{
    ScriptApp.deleteTrigger(triggers[i]);
  }}
  ScriptApp.newTrigger("onFormSubmitHandler")
    .forForm("{form_id}")
    .onFormSubmit()
    .create();
  FormApp.openById("{form_id}").setBackgroundColor("{bg_color}");
}}
"""

_APPS_SCRIPT_MANIFEST = {
    "timeZone": "Europe/Madrid",
    "dependencies": {},
    "exceptionLogging": "STACKDRIVER",
    "runtimeVersion": "V8",
    "executionApi": {"access": "MYSELF"},
    "oauthScopes": [
        "https://www.googleapis.com/auth/forms.currentonly",
        "https://www.googleapis.com/auth/script.external_request",
        "https://www.googleapis.com/auth/script.scriptapp",
    ],
}

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
    bg_color: str = ""


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

        self._backend_url = (
            os.environ.get("BACKEND_URL", "https://api.machango.org").rstrip("/")
            + "/api/form-submission"
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
        self._creds = creds

        self._forms  = build("forms",  "v1", credentials=creds, cache_discovery=False)
        self._sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
        self._drive  = build("drive",  "v3", credentials=creds, cache_discovery=False)
        # Apps Script requiere scope 'script.projects' en el refresh token.
        # Si no está autorizado, se inicializa a None y deploy_submit_webhook es no-op.
        try:
            self._script = build("script", "v1", credentials=creds, cache_discovery=False)
        except Exception:
            self._script = None

    # ------------------------------------------------------------------

    def create_form_for_open_mic(
        self,
        open_mic_id: str,
        nombre: str,
        info: dict | None = None,
    ) -> FormCreationResult:
        """
        1. Crea el Google Form con descripción contextual y color aleatorio.
        2. Añade preguntas (fechas como checkbox si hay cadencia).
        3. Activa la recogida de respuestas en Sheet.
        4. Inyecta columna open_mic_id con ARRAYFORMULA en la Sheet.
        5. Devuelve FormCreationResult con URLs, IDs y bg_color.
        """
        info = info or {}
        bg_color = self._random_form_color()
        form_id = self._create_form(nombre, info, bg_color)
        self._add_questions(form_id, info)
        sheet_id = self._get_linked_sheet_id(form_id, nombre)
        self._inject_open_mic_id_column(sheet_id, open_mic_id)
        try:
            self.deploy_submit_webhook(form_id=form_id, open_mic_id=open_mic_id, bg_color=bg_color)
        except Exception as e:
            print(f"[GoogleFormBuilder] Apps Script webhook no desplegado: {e}")

        form_url = f"https://docs.google.com/forms/d/{form_id}/viewform"
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"

        return FormCreationResult(
            form_id=form_id,
            form_url=form_url,
            sheet_id=sheet_id,
            sheet_url=sheet_url,
            bg_color=bg_color,
        )

    # ------------------------------------------------------------------
    # Pasos internos
    # ------------------------------------------------------------------

    def _create_form(self, nombre: str, info: dict | None = None, bg_color: str = "") -> str:
        """Crea el form con descripción contextual y devuelve su form_id."""
        info = info or {}
        body = {
            "info": {
                "title": f"Solicitudes — {nombre}",
                "description": self._build_description(nombre, info),
            }
        }
        result = self._forms.forms().create(body=body).execute()
        return result["formId"]

    def _add_questions(self, form_id: str, info: dict | None = None) -> None:
        """Añade los campos via batchUpdate.

        Si cadencia == 'unico' o no hay cadencia: omite la pregunta de fechas.
        Si hay cadencia con fechas: usa CHECKBOX en lugar de texto libre.
        """
        info = info or {}
        dates = self._build_date_options(info)
        cadencia = info.get("cadencia", "")

        requests = []
        idx = 0
        for q in _FORM_QUESTIONS:
            # Pregunta de fechas: sustituir o eliminar según cadencia
            if "fecha" in q["title"].lower() and q["kind"] == "textQuestion":
                if cadencia == "unico":
                    # Evento único: omitir la pregunta
                    continue
                elif cadencia and dates:
                    # Con cadencia y fechas calculadas: convertir a CHECKBOX
                    item = {
                        "title": q["title"],
                        "questionItem": {
                            "question": {
                                "required": q["required"],
                                "choiceQuestion": {
                                    "type": "CHECKBOX",
                                    "options": [{"value": d} for d in dates],
                                },
                            }
                        },
                    }
                else:
                    # Sin cadencia (legacy) o cadencia con fechas vacías: mantener texto libre
                    item = self._build_item(q)
            else:
                item = self._build_item(q)

            requests.append({
                "createItem": {
                    "item": item,
                    "location": {"index": idx},
                }
            })
            idx += 1

        self._forms.forms().batchUpdate(
            formId=form_id,
            body={"requests": requests},
        ).execute()

    # ------------------------------------------------------------------
    # Sprint 13 — helpers de descripción, color y fechas
    # ------------------------------------------------------------------

    def _random_form_color(self) -> str:
        """Elige un color aleatorio de la paleta curada."""
        return random.choice(_FORM_BG_PALETTE)

    @staticmethod
    def _build_description(nombre: str, info: dict) -> str:
        """Genera la descripción contextual del form a partir del info del open mic."""
        parts = [f"Formulario de inscripción al Open mic de comedia {nombre}"]
        if info.get("local"):
            parts.append(f"en {info['local']}")
        if info.get("direccion"):
            parts.append(f"en la calle {info['direccion']}")
        if info.get("dia_semana"):
            cadencia_label = {
                "semanal":   "semanalmente",
                "quincenal": "cada dos semanas",
                "mensual":   "mensualmente",
                "unico":     "",
            }.get(info.get("cadencia", ""), "")
            dia_str = info["dia_semana"]
            if cadencia_label:
                dia_str += f" {cadencia_label}"
            parts.append(f"los {dia_str}")
        return " ".join(parts)

    def _build_date_options(self, info: dict) -> list[str]:
        """Calcula las fechas seleccionables según la cadencia del open mic.

        Devuelve lista de strings "dd-MM-YY". Devuelve [] para evento único o sin cadencia.
        """
        cadencia = info.get("cadencia", "")
        if not cadencia or cadencia == "unico":
            return []

        today = dt.date.today()

        if cadencia == "semanal":
            dia_nombre = info.get("dia_semana", "")
            weekday_target = _DIA_SEMANA_MAP.get(dia_nombre)
            if weekday_target is None:
                return []
            # Todos los [dia_semana] del mes actual >= hoy
            year, month = today.year, today.month
            last_day = calendar.monthrange(year, month)[1]
            dates = []
            for day in range(1, last_day + 1):
                d = dt.date(year, month, day)
                if d.weekday() == weekday_target and d >= today:
                    dates.append(d.strftime("%d-%m-%y"))
            return dates

        fecha_inicio_str = info.get("fecha_inicio", "")
        try:
            start = dt.date.fromisoformat(fecha_inicio_str) if fecha_inicio_str else today
        except ValueError:
            start = today

        if cadencia == "quincenal":
            # Avanzar de 14 en 14 días desde start hasta tener 4 fechas >= hoy
            dates: list[str] = []
            current = start
            # Alinear con today si start está en el pasado
            while current < today:
                current += dt.timedelta(days=14)
            for _ in range(4):
                dates.append(current.strftime("%d-%m-%y"))
                current += dt.timedelta(days=14)
            return dates

        if cadencia == "mensual":
            # Próximas 3 fechas, mismo día del mes, sumando 1 mes
            dates = []
            current = start
            # Avanzar hasta tener una fecha >= hoy
            while current < today:
                year_c = current.year + (current.month // 12)
                month_c = (current.month % 12) + 1
                day_c = min(current.day, calendar.monthrange(year_c, month_c)[1])
                current = dt.date(year_c, month_c, day_c)
            for _ in range(3):
                dates.append(current.strftime("%d-%m-%y"))
                year_c = current.year + (current.month // 12)
                month_c = (current.month % 12) + 1
                day_c = min(current.day, calendar.monthrange(year_c, month_c)[1])
                current = dt.date(year_c, month_c, day_c)
            return dates

        return []

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

    def deploy_submit_webhook(self, form_id: str, open_mic_id: str, bg_color: str = "") -> str:
        """
        Crea un Apps Script bound al form con un trigger installable onFormSubmit
        que hace POST al backend con los datos del formulario + open_mic_id.

        Pasos:
          1. Crea proyecto Apps Script asociado al form (parentId).
          2. Sube el código (Code.gs + appsscript.json manifest).
          3. Crea una deployment como API executable.
          4. Llama a scripts.run("setup") para instalar el trigger installable.

        Returns: script_id del proyecto creado.
        """
        if self._script is None:
            raise RuntimeError(
                "Apps Script no disponible. Regenera el refresh token con scope "
                "'https://www.googleapis.com/auth/script.projects' usando "
                "backend/scripts/google_oauth_setup.py"
            )

        # 1. Crear proyecto bound al form
        project = self._script.projects().create(body={
            "title": f"Webhook — {form_id}",
            "parentId": form_id,
        }).execute()
        script_id = project["scriptId"]

        # 2. Subir código
        code = _APPS_SCRIPT_TEMPLATE.format(
            open_mic_id=open_mic_id,
            backend_url=self._backend_url,
            form_id=form_id,
            api_key=os.environ.get("WEBHOOK_API_KEY", ""),
            bg_color=bg_color or "#E8EAED",
        )
        self._script.projects().updateContent(
            scriptId=script_id,
            body={
                "files": [
                    {
                        "name": "appsscript",
                        "type": "JSON",
                        "source": json.dumps(_APPS_SCRIPT_MANIFEST),
                    },
                    {
                        "name": "Code",
                        "type": "SERVER_JS",
                        "source": code,
                    },
                ]
            },
        ).execute()

        # 3. Crear deployment como API executable (necesario para scripts.run)
        self._script.projects().deployments().create(
            scriptId=script_id,
            body={
                "versionNumber": -1,
                "manifestFileName": "appsscript",
                "description": "API executable — form webhook",
            },
        ).execute()

        # 4. Ejecutar setup() para instalar el trigger installable
        self._script.scripts().run(
            scriptId=script_id,
            body={"function": "setup"},
        ).execute()

        return script_id

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
            ["open_mic_id", "n8n_procesado"],
            [f'=ARRAYFORMULA(SI(B2:B<>"";"{open_mic_id}";""))'],
        ]

        self._sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{sheet_name}!J1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
