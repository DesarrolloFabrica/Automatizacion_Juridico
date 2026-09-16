"""
Pipeline Jurídico (Consultorio Jurídico) → esquema legal_consulting.

  Excel plano (2 hojas) → CSV/xlsx normalizados → SQL 01/02/03
  Opcional: cargar a Postgres (local legal_dev). CORE/prod exige --permitir-prod.

Independiente del pipeline de tickets (pipeline_zarigueya/): no comparte
catálogos, columnas ni reglas de negocio con Zarigüeya. No modifica CORE.

Uso (PowerShell, carpeta pipeline_juridico):

  python pipeline.py "..\\juridico\\CONTROL DE USUARIOS A-C.xlsx"
  python pipeline.py ".\\nuevo_lote.xlsx" --cargar
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from generar_sql_carga import generar
from normalizar_juridico import normalizar

BASE = Path(__file__).resolve().parent


def validar_carga(conn) -> None:
    """Cuenta filas cargadas y las compara contra lo que se acaba de generar,
    como último chequeo antes de dar la carga por buena."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM legal_consulting.consulta;")
        n_consulta = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM legal_consulting.proceso_judicial;")
        n_proceso = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM legal_consulting.estudiante_consultorio;")
        n_estudiante = cur.fetchone()[0]
    print(f"consultas en BD: {n_consulta}")
    print(f"procesos_judiciales en BD: {n_proceso}")
    print(f"estudiantes_consultorio en BD: {n_estudiante}")


def cargar_postgres(*, permitir_prod: bool) -> None:
    import psycopg2

    load_dotenv(BASE / ".env")
    host = os.getenv("LEGAL_DB_HOST", "localhost")
    port = os.getenv("LEGAL_DB_PORT", "5432")
    name = os.getenv("LEGAL_DB_NAME", "legal_dev")
    user = os.getenv("LEGAL_DB_USER", "postgres")
    password = os.getenv("LEGAL_DB_PASSWORD", "")

    if name.lower() == "core" and not permitir_prod:
        raise SystemExit(
            "LEGAL_DB_NAME=core es productivo. No se carga sin --permitir-prod."
        )

    conn = psycopg2.connect(
        host=host, port=port, dbname=name, user=user, password=password
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for archivo in (
                "01_legal_consulting_schema.sql",
                "02_cargar_catalogos.sql",
                "03_cargar_juridico.sql",
            ):
                sql = (BASE / archivo).read_text(encoding="utf-8")
                print(f"ejecutando {archivo} …")
                cur.execute(sql)
                print(f"ok {archivo}")
        validar_carga(conn)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline de normalización Jurídico (Consultorio Jurídico) → legal_consulting"
    )
    parser.add_argument("excel", help="Ruta al .xlsx de Jurídico (hojas CONTROL DE USUARIOS + PROCESOS ...)")
    parser.add_argument(
        "--cargar",
        action="store_true",
        help="Después de normalizar, ejecuta 01+02+03 en Postgres (.env)",
    )
    parser.add_argument(
        "--permitir-prod",
        action="store_true",
        help="Permite cargar si LEGAL_DB_NAME=core (GCP). Por defecto bloqueado.",
    )
    parser.add_argument(
        "--forzar-carga-con-criticas",
        action="store_true",
        help="Salta el freno de advertencias críticas (no recomendado).",
    )
    args = parser.parse_args()
    excel = Path(args.excel)
    if not excel.exists():
        raise SystemExit(f"No existe: {excel}")

    print("1/3 normalizar Excel → CSV")
    stats = normalizar(excel, BASE)
    print(stats)
    n_criticas = stats.get("advertencias_criticas", 0)
    if stats.get("advertencias"):
        print(
            f"AVISO: {stats['advertencias']} advertencia(s) de calidad ({n_criticas} crítica(s)) "
            "en advertencias_calidad.csv — revísalas antes de cargar a producción."
        )

    print("2/3 generar SQL de carga")
    generar()
    print("   (03b_cargar_procesos_MANUAL.sql se genera pero NO se ejecuta solo -- ver LEEME.txt)")

    if args.cargar:
        if n_criticas and not args.forzar_carga_con_criticas:
            raise SystemExit(
                f"BLOQUEADO: {n_criticas} advertencia(s) crítica(s) (dato sin el tipo esperado). "
                "No se carga nada. Revisa advertencias_calidad.csv, corrige el Excel de origen y "
                "vuelve a correr. Si de verdad quieres saltarte esto, usa --forzar-carga-con-criticas."
            )
        print("3/3 cargar a Postgres")
        cargar_postgres(permitir_prod=args.permitir_prod)
    else:
        print("3/3 carga omitida (pasa --cargar para Postgres local)")
        print("SQL listo: 01_legal_consulting_schema.sql, 02_cargar_catalogos.sql, 03_cargar_juridico.sql")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
