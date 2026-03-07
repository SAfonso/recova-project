"""FormIngestor — lee respuestas de un Google Form via Forms API.

No requiere sheet vinculado ni Apps Script.
Aplica un field_mapping para traducir títulos de preguntas al schema canónico.
Campos sin mapeo van a metadata_extra.

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
    "https://www.googleapis.com/auth/forms.body.readonly",
    "https://www.googleapis.com/auth/forms.responses.readonly",
]


class FormIngestor:

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
        self._forms = build("forms", "v1", credentials=creds, cache_discovery=False)

    # ------------------------------------------------------------------

    def get_form_questions(self, form_id: str) -> list[dict]:
        """
        Devuelve la lista de preguntas del form.
        Cada dict: {question_id, title, kind}.
        Items sin questionItem (secciones, imágenes) se ignoran.
        """
        form = self._forms.forms().get(formId=form_id).execute()
        questions = []
        for item in form.get("items", []):
            question_item = item.get("questionItem")
            if not question_item:
                continue
            question = question_item.get("question", {})
            question_id = question.get("questionId", "")
            title = item.get("title", "")
            kind = "choiceQuestion" if "choiceQuestion" in question else "textQuestion"
            questions.append({"question_id": question_id, "title": title, "kind": kind})
        return questions

    def get_responses(
        self,
        form_id: str,
        field_mapping: dict[str, str | None],
    ) -> list[dict]:
        """
        Lee todas las respuestas del form y las normaliza aplicando field_mapping.

        - Campos con mapeo canónico → dict raíz
        - Campos con mapeo None o sin entry en field_mapping → metadata_extra
        - Incluye _response_id y _submitted_at
        """
        # Construir índice question_id → title
        questions = self.get_form_questions(form_id)
        id_to_title = {q["question_id"]: q["title"] for q in questions}

        responses_result = (
            self._forms.forms().responses().list(formId=form_id).execute()
        )
        results = []
        for resp in responses_result.get("responses", []):
            normalized: dict = {
                "_response_id": resp.get("responseId", ""),
                "_submitted_at": resp.get("createTime", ""),
                "metadata_extra": {},
            }

            for qid, answer_obj in resp.get("answers", {}).items():
                title = id_to_title.get(qid, qid)
                value = self._extract_value(answer_obj)
                canonical = field_mapping.get(title)

                if canonical is not None and title in field_mapping:
                    normalized[canonical] = value
                else:
                    normalized["metadata_extra"][title] = value

            results.append(normalized)
        return results

    # ------------------------------------------------------------------

    @staticmethod
    def _extract_value(answer_obj: dict) -> str:
        """Extrae el valor de texto de una respuesta de Forms API."""
        text_answers = answer_obj.get("textAnswers", {})
        answers = text_answers.get("answers", [])
        if not answers:
            return ""
        # Múltiple selección → unir con coma; único → string plano
        return ", ".join(a.get("value", "") for a in answers)
