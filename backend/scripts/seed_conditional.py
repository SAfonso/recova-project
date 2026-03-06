"""seed_conditional.py — inserta 10 cómicos aleatorios en open mics sin solicitudes.

Lee todos los open mics existentes en silver. Para cada uno que no tenga
solicitudes en silver.solicitudes, genera e inserta:
  - 10 silver.comicos (ON CONFLICT por instagram)
  - 10 bronze.solicitudes
  - 10 silver.solicitudes

Uso:
    python backend/scripts/seed_conditional.py
"""

from __future__ import annotations

import os
import random
import uuid
from datetime import date, timedelta
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

_CATEGORIAS = ["general"] * 5 + ["priority"] * 3 + ["gold"] * 1 + ["restricted"] * 1

_ORIGENES = ["instagram", "referido", "whatsapp", "amigos", "cartel"]


def _slug(nombre: str) -> str:
    tr = str.maketrans("áéíóúñÁÉÍÓÚÑ", "aeiounAEIOUN")
    return nombre.lower().translate(tr).replace(" ", "_")


def _next_friday() -> date:
    today = date.today()
    days_ahead = (4 - today.weekday()) % 7 or 7
    return today + timedelta(days=days_ahead)


def _insert_batch(cur, open_mic_id: str, proveedor_id: str, nombres: list[str]) -> None:
    cats = _CATEGORIAS[:]
    random.shuffle(cats)
    prefix = str(open_mic_id)[:8]
    fecha = _next_friday()
    sheet_row_base = random.randint(2000, 9000)

    for i, nombre in enumerate(nombres):
        instagram = f"{_slug(nombre)}_{prefix}"[:50]
        telefono = f"+346{random.randint(10000000, 99999999)}"
        categoria = cats[i % len(cats)]
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

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT om.id, om.proveedor_id, om.nombre,
                       COUNT(s.id) AS total_solicitudes
                FROM silver.open_mics om
                LEFT JOIN silver.solicitudes s ON s.open_mic_id = om.id
                GROUP BY om.id, om.proveedor_id, om.nombre
                """
            )
            open_mics = cur.fetchall()

        if not open_mics:
            print("No hay open mics en la base de datos.")
            return

        seeded = 0
        with conn.cursor() as cur:
            for om_id, prov_id, nombre, total in open_mics:
                if total > 0:
                    print(f"  [skip] {nombre} — ya tiene {total} solicitudes")
                    continue

                print(f"  [seed] {nombre} — insertando 10 comicos...")
                nombres = random.sample(_NOMBRES, 10)
                _insert_batch(cur, om_id, prov_id, nombres)
                seeded += 1

        conn.commit()
        if seeded:
            print(f"\nSeed condicional completado: {seeded} open mic(s) rellenados.")
        else:
            print("\nTodos los open mics ya tenían solicitudes. Nada que insertar.")
    except Exception as exc:
        conn.rollback()
        raise RuntimeError("Error en seed condicional. Rollback ejecutado.") from exc
    finally:
        conn.close()


if __name__ == "__main__":
    main()
