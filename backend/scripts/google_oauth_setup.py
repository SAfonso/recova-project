"""Script de autorización OAuth2 de Google (ejecución única).

Uso:
    python backend/scripts/google_oauth_setup.py --client-secrets /ruta/client_secret.json

Abre el navegador para que autorices el acceso. Al terminar imprime
el refresh_token y los valores que hay que añadir al .env.
"""

import argparse
import json

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client-secrets",
        required=True,
        help="Ruta al JSON de credenciales OAuth2 descargado de Google Cloud",
    )
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(args.client_secrets, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(args.client_secrets) as f:
        client_info = json.load(f)

    installed = client_info.get("installed") or client_info.get("web", {})

    print("\n✅ Autorización completada. Añade esto al backend/.env:\n")
    print(f"GOOGLE_OAUTH_CLIENT_ID={installed['client_id']}")
    print(f"GOOGLE_OAUTH_CLIENT_SECRET={installed['client_secret']}")
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
