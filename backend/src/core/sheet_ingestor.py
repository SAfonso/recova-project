"""SheetIngestor — lee filas pendientes de una Google Sheet y las marca como procesadas.

La columna K (n8n_procesado) actúa como flag de control:
  - vacía  → fila pendiente de ingestar
  - "si"   → ya procesada, se ignora

Variables de entorno:
    GOOGLE_OAUTH_CLIENT_ID
    GOOGLE_OAUTH_CLIENT_SECRET
    GOOGLE_OAUTH_REFRESH_TOKEN
"""

from __future__ import annotations

import os

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

_PROCESADO_COL = "K"
_PROCESADO_HEADER = "n8n_procesado"


class SheetIngestor:

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
            scopes=_SCOPES,
        )
        creds.refresh(Request())
        self._sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

    def get_pending_rows(self, sheet_id: str) -> list[dict]:
        """
        Devuelve las filas con n8n_procesado vacío.
        Cada dict incluye _row_number (1-based, contando cabecera como fila 1).
        """
        result = (
            self._sheets.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range="A:K")
            .execute()
        )
        all_rows = result.get("values", [])
        if len(all_rows) < 2:
            return []

        headers = all_rows[0]
        pending = []

        for i, row in enumerate(all_rows[1:], start=2):  # fila 2 en adelante
            # Rellenar columnas faltantes con cadena vacía
            padded = row + [""] * (len(headers) - len(row))
            row_dict = dict(zip(headers, padded))

            # Solo filas reales (con Marca temporal) y no procesadas
            if row_dict.get("Marca temporal", "") and not row_dict.get(_PROCESADO_HEADER, ""):
                row_dict["_row_number"] = i
                pending.append(row_dict)

        return pending

    def mark_rows_processed(self, sheet_id: str, row_numbers: list[int]) -> None:
        """Escribe 'si' en columna K para cada fila indicada."""
        if not row_numbers:
            return

        data = [
            {"range": f"{_PROCESADO_COL}{n}", "values": [["si"]]}
            for n in row_numbers
        ]
        self._sheets.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={"valueInputOption": "RAW", "data": data},
        ).execute()
