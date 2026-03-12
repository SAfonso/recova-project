"""seed_full.py — crea un escenario de prueba completo desde cero.

Inserta:
  - 1 silver.proveedores (slug único con fecha)
  - 3 silver.open_mics asociados a ese proveedor
  - 30 silver.comicos distintos (10 por open mic)
  - 30 bronze.solicitudes + 30 silver.solicitudes

Uso:
    python backend/scripts/seed_full.py
"""

from __future__ import annotations

import os
import random
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]

_NOMBRES = [
    "Ana García", "Carlos López", "María Fernández", "Pedro Martínez",
    "Laura Sánchez", "Juan González", "Elena Torres", "Miguel Ruiz",
    "Sofía Moreno", "David Jiménez", "Carmen Díaz", "Rafael Molina",
    "Patricia Romero", "Alberto Serrano", "Isabel Navarro", "Sergio Blanco",
    "Lucía Castillo", "Fernando Vega", "Marta Ramos", "Andrés Suárez",
    "Beatriz Herrero", "Ricardo Medina", "Natalia Guerrero", "Javier Cano",
    "Cristina Aguilar", "Pablo Domínguez", "Rosa León", "Alejandro Mora",
    "Teresa Delgado", "Óscar Vargas",
]

_EXPERIENCIAS = [
    ("Es mi primera vez",                  1),
    ("He probado alguna vez",              2),
    ("Llevo tiempo haciendo stand-up",     3),
    ("Soy un profesional / tengo cachés", 4),
]

_CATEGORIAS_PER_MIC = (
    ["general"] * 5 + ["priority"] * 3 + ["gold"] * 1 + ["restricted"] * 1
)

_ORIGENES = ["instagram", "referido", "whatsapp", "amigos", "cartel"]

_DEFAULT_CONFIG = """{
  "available_slots": 8,
  "categories": {
    "standard":   {"base_score": 50,  "enabled": true},
    "priority":   {"base_score": 70,  "enabled": true},
    "gold":       {"base_score": 90,  "enabled": true},
    "restricted": {"base_score": null,"enabled": true}
  },
  "recency_penalty":   {"enabled": true,  "last_n_editions": 2, "penalty_points": 20},
  "single_date_boost": {"enabled": true,  "boost_points": 10},
  "gender_parity":     {"enabled": false, "target_female_nb_pct": 40}
}"""

_OM_NAMES = ["Open Mic A", "Open Mic B", "Open Mic C"]


def _slug(nombre: str) -> str:
    tr = str.maketrans("áéíóúñÁÉÍÓÚÑ", "aeiounAEIOUN")
    return nombre.lower().translate(tr).replace(" ", "_")


def _next_friday() -> date:
    today = date.today()
    days_ahead = (4 - today.weekday()) % 7 or 7
    return today + timedelta(days=days_ahead)


def _insert_batch(cur, open_mic_id: str, proveedor_id: str, nombres: list[str]) -> None:
    cats = list(_CATEGORIAS_PER_MIC)
    prefix = str(open_mic_id)[:8]
    fecha = _next_friday()
    sheet_row_base = random.randint(2000, 9000)

    for i, nombre in enumerate(nombres):
        instagram = f"{_slug(nombre)}_{prefix}"[:50]
        telefono = f"+346{random.randint(10000000, 99999999)}"
        categoria = cats[i]
        exp_raw, niv = random.choice(_EXPERIENCIAS)
        disponible = random.choice([True, False])
        origen = random.choice(_ORIGENES)
        comico_id = str(uuid.uuid4())
        bronze_id = str(uuid.uuid4())
        silver_id = str(uuid.uuid4())

        cur.execute(
            """
            INSERT INTO silver.comicos (id, instagram, nombre, telefono, categoria, metadata_comico)
            VALUES (%s, %s, %s, %s, %s, '{}'::jsonb)
            ON CONFLICT (instagram) DO UPDATE SET id = silver.comicos.id
            RETURNING id
            """,
            (comico_id, instagram, nombre, telefono, categoria),
        )
        real_comico_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO bronze.solicitudes (
                id, proveedor_id, open_mic_id, sheet_row_id,
                nombre_raw, instagram_raw, telefono_raw,
                experiencia_raw, fechas_seleccionadas_raw,
                disponibilidad_ultimo_minuto, info_show_cercano,
                origen_conocimiento, raw_data_extra, procesado
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'{"seed":true}'::jsonb,true)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                bronze_id, proveedor_id, open_mic_id, sheet_row_base + i,
                nombre, "@" + instagram, telefono,
                exp_raw, str(fecha),
                disponible, None, origen,
            ),
        )

        cur.execute(
            """
            INSERT INTO silver.solicitudes (
                id, bronze_id, proveedor_id, open_mic_id, comico_id,
                fecha_evento, nivel_experiencia, disponibilidad_ultimo_minuto,
                status, metadata_ia
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'normalizado','{"seed":true}'::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                silver_id, bronze_id, proveedor_id, open_mic_id,
                real_comico_id, fecha, niv, disponible,
            ),
        )


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("No se encontró DATABASE_URL en .env")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    prov_id = str(uuid.uuid4())
    prov_nombre = f"Test Venue {timestamp}"
    prov_slug = f"test-venue-{timestamp}"

    # 30 nombres únicos mezclados
    nombres_pool = list(_NOMBRES)
    random.shuffle(nombres_pool)

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO silver.proveedores (id, nombre_comercial, slug) VALUES (%s, %s, %s)",
                (prov_id, prov_nombre, prov_slug),
            )
            print(f"Proveedor creado: {prov_nombre} (id: {prov_id})")

            for idx, om_name in enumerate(_OM_NAMES, start=1):
                om_id = str(uuid.uuid4())
                full_name = f"{prov_nombre} — {om_name}"
                cur.execute(
                    "INSERT INTO silver.open_mics (id, proveedor_id, nombre, config) VALUES (%s,%s,%s,%s::jsonb)",
                    (om_id, prov_id, full_name, _DEFAULT_CONFIG),
                )
                batch = nombres_pool[(idx - 1) * 10 : idx * 10]
                _insert_batch(cur, om_id, prov_id, batch)
                print(f"Open mic {idx}: {full_name} — 10 comicos insertados")

        conn.commit()
        print(f"\nSeed completo: 3 open mics, 30 comicos, 30 bronze, 30 silver.")
    except Exception as exc:
        conn.rollback()
        raise RuntimeError("Error en seed_full. Rollback ejecutado.") from exc
    finally:
        conn.close()


if __name__ == "__main__":
    main()
