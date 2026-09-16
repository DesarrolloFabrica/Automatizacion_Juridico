"""Genera 02_cargar_catalogos.sql, 03_cargar_juridico.sql y
03b_cargar_procesos_MANUAL.sql a partir de los CSV normalizados por normalizar_juridico.py.

MODO ACUMULAR (piloto de automatización, sep 2026): catálogos + consulta usan UPSERT
(INSERT ... ON CONFLICT ... DO UPDATE/NOTHING) por llave natural, igual que Diplomados.
Los FK se resuelven con subconsultas por código/nombre, no con ids fijos.

Excepción a propósito: proceso_judicial NO tiene llave natural en el Excel de origen (no
trae número de expediente/radicado) -- por eso su carga sigue en un archivo APARTE
(03b_cargar_procesos_MANUAL.sql) que se sigue corriendo a mano, con el modo viejo
(TRUNCATE + recarga completa). No lo ejecuta el robot de la automatización.
"""

from __future__ import annotations

import csv
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT_CAT = BASE / "02_cargar_catalogos.sql"
OUT_HECHOS = BASE / "03_cargar_juridico.sql"
OUT_PROCESOS_MANUAL = BASE / "03b_cargar_procesos_MANUAL.sql"


def sql_str(value: str | None) -> str:
    if value is None or value == "":
        return "NULL"
    tag = "lc"
    n = 0
    while f"${tag}$" in value:
        n += 1
        tag = f"lc{n}"
    return f"${tag}${value}${tag}$"


def sql_str_or_empty(value: str | None) -> str:
    """Como sql_str, pero '' se guarda como texto vacío real, no NULL. Necesario para
    columnas NOT NULL DEFAULT '' que además son parte de una llave natural compuesta
    (ej. consulta.ticket_externo) -- NULL nunca es igual a sí mismo en SQL, así que dos
    filas con NULL jamás se detectarían como duplicadas."""
    if value is None:
        return "NULL"
    if value == "":
        return "''"
    tag = "lc"
    n = 0
    while f"${tag}$" in value:
        n += 1
        tag = f"lc{n}"
    return f"${tag}${value}${tag}$"


def sql_bool(value: str | None) -> str:
    if value is None or str(value).strip() == "":
        return "NULL"
    return "TRUE" if str(value).strip().lower() in {"true", "1", "t"} else "FALSE"


def sql_date(value: str | None) -> str:
    if value is None or str(value).strip() == "":
        return "NULL"
    return f"DATE {sql_str(str(value).strip())}"


def rows_of(name: str) -> list[dict[str, str]]:
    path = BASE / name
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def generar(base_dir: str | Path | None = None) -> None:
    global BASE, OUT_CAT, OUT_HECHOS, OUT_PROCESOS_MANUAL
    if base_dir is not None:
        BASE = Path(base_dir)
        OUT_CAT = BASE / "02_cargar_catalogos.sql"
        OUT_HECHOS = BASE / "03_cargar_juridico.sql"
        OUT_PROCESOS_MANUAL = BASE / "03b_cargar_procesos_MANUAL.sql"

    # -------------------------------------------------------------------
    # 02_cargar_catalogos.sql -- UPSERT por llave natural
    # -------------------------------------------------------------------
    lines: list[str] = [
        "-- Carga (UPSERT) de catálogos + estudiante_consultorio. Ejecutar DESPUÉS de",
        "-- 01_legal_consulting_schema.sql. MODO ACUMULAR: no borra nada.",
        "BEGIN;",
        "",
    ]

    for row in rows_of("periodo_academico.csv"):
        lines.append(
            "INSERT INTO legal_consulting.periodo_academico (codigo, letra_origen, anio) VALUES "
            f"({sql_str(row['codigo'])}, {sql_str(row['letra_origen'])}, {row['anio']}) "
            "ON CONFLICT (codigo) DO UPDATE SET letra_origen = EXCLUDED.letra_origen, anio = EXCLUDED.anio;"
        )
    lines.append("")

    for row in rows_of("area_derecho.csv"):
        lines.append(
            f"INSERT INTO legal_consulting.area_derecho (nombre) VALUES ({sql_str(row['nombre'])}) "
            "ON CONFLICT (nombre) DO NOTHING;"
        )
    lines.append("")

    for row in rows_of("modalidad_atencion.csv"):
        lines.append(
            f"INSERT INTO legal_consulting.modalidad_atencion (nombre) VALUES ({sql_str(row['nombre'])}) "
            "ON CONFLICT (nombre) DO NOTHING;"
        )
    lines.append("")

    for row in rows_of("estado_caso.csv"):
        # codigo == nombre (mismo valor, ver normalizar_juridico.py)
        lines.append(
            "INSERT INTO legal_consulting.estado_caso (codigo, nombre) VALUES "
            f"({sql_str(row['codigo'])}, {sql_str(row['codigo'])}) ON CONFLICT (codigo) DO NOTHING;"
        )
    lines.append("")

    for row in rows_of("tipo_proceso.csv"):
        lines.append(
            "INSERT INTO legal_consulting.tipo_proceso (nombre_normalizado, nombre_origen) VALUES "
            f"({sql_str(row['nombre_normalizado'])}, {sql_str(row['nombre_origen'])}) "
            "ON CONFLICT (nombre_normalizado) DO UPDATE SET nombre_origen = EXCLUDED.nombre_origen;"
        )
    lines.append("")

    for row in rows_of("estudiante_consultorio.csv"):
        # OJO: core_person_id/match_status NUNCA se tocan aquí -- los llena el proceso de
        # cruce con CORE; si el UPSERT los reescribiera, cada recarga perdería ese trabajo.
        lines.append(
            "INSERT INTO legal_consulting.estudiante_consultorio (nombre_origen, nombre_normalizado) VALUES "
            f"({sql_str(row['nombre_origen'])}, {sql_str(row['nombre_normalizado'])}) "
            "ON CONFLICT (nombre_normalizado) DO UPDATE SET nombre_origen = EXCLUDED.nombre_origen;"
        )
    lines += ["", "COMMIT;", ""]
    OUT_CAT.write_text("\n".join(lines), encoding="utf-8")

    # -------------------------------------------------------------------
    # 03_cargar_juridico.sql -- UPSERT de consulta (la única automatizable)
    # -------------------------------------------------------------------
    hechos: list[str] = [
        "-- Carga (UPSERT) de consulta. Ejecutar DESPUÉS de 02_cargar_catalogos.sql.",
        "-- MODO ACUMULAR: llave natural = (ticket, fecha, hora, area, estudiante, modalidad,",
        "-- estado). Si esa combinación ya existe, se ignora (no duplica); si es nueva, se",
        "-- inserta. proceso_judicial NO va aquí -- ver 03b_cargar_procesos_MANUAL.sql.",
        "BEGIN;",
        "",
    ]

    for row in rows_of("consulta.csv"):
        periodo_sub = f"(SELECT id FROM legal_consulting.periodo_academico WHERE codigo = {sql_str(row['periodo_codigo'])})"
        area_sub = f"(SELECT id FROM legal_consulting.area_derecho WHERE nombre = {sql_str(row['area_derecho_nombre'])})"
        estudiante_sub = f"(SELECT id FROM legal_consulting.estudiante_consultorio WHERE nombre_normalizado = {sql_str(row['estudiante_normalizado'])})"
        modalidad_sub = f"(SELECT id FROM legal_consulting.modalidad_atencion WHERE nombre = {sql_str(row['modalidad_nombre'])})"
        estado_sub = f"(SELECT id FROM legal_consulting.estado_caso WHERE codigo = {sql_str(row['estado_codigo'])})"
        hechos.append(
            "INSERT INTO legal_consulting.consulta ("
            "ticket_externo, fecha, hora_texto, periodo_id, area_derecho_id, "
            "estudiante_id, modalidad_id, estado_id"
            ") VALUES ("
            f"{sql_str_or_empty(row['ticket_externo'])}, {sql_date(row['fecha'])}, {sql_str_or_empty(row['hora_texto'])}, "
            f"{periodo_sub}, {area_sub}, {estudiante_sub}, {modalidad_sub}, {estado_sub}"
            ") ON CONFLICT (ticket_externo, fecha, hora_texto, area_derecho_id, estudiante_id, "
            "modalidad_id, estado_id) DO UPDATE SET updated_at = now();"
        )
    hechos += ["", "COMMIT;", ""]
    OUT_HECHOS.write_text("\n".join(hechos), encoding="utf-8")

    # -------------------------------------------------------------------
    # 03b_cargar_procesos_MANUAL.sql -- proceso_judicial, modo viejo (TRUNCATE+recarga)
    # -------------------------------------------------------------------
    procesos: list[str] = [
        "-- Carga de proceso_judicial. SOLO A MANO -- el robot de la automatización NO",
        "-- ejecuta este archivo (ver LEEME.txt / 01_legal_consulting_schema.sql: esta tabla",
        "-- no tiene llave natural en el Excel de origen, así que no se puede acumular sin",
        "-- riesgo de duplicar). Revisa el resultado antes de correrlo contra producción.",
        "-- TRUNCATE: cada corrida reemplaza TODA la tabla, no la acumula.",
        "BEGIN;",
        "TRUNCATE TABLE legal_consulting.proceso_judicial RESTART IDENTITY;",
        "",
    ]

    for row in rows_of("proceso_judicial.csv"):
        area_sub = f"(SELECT id FROM legal_consulting.area_derecho WHERE nombre = {sql_str(row['area_derecho_nombre'])})"
        estudiante_sub = f"(SELECT id FROM legal_consulting.estudiante_consultorio WHERE nombre_normalizado = {sql_str(row['estudiante_normalizado'])})"
        estado_sub = f"(SELECT id FROM legal_consulting.estado_caso WHERE codigo = {sql_str(row['estado_codigo'])})"
        tipo_sub = f"(SELECT id FROM legal_consulting.tipo_proceso WHERE nombre_normalizado = {sql_str(row['tipo_proceso_nombre'])})"
        procesos.append(
            "INSERT INTO legal_consulting.proceso_judicial ("
            "area_derecho_id, poder_sustitucion, estudiante_id, estado_id, "
            "estado_observacion, tipo_proceso_id, etapa_texto, etapa_fecha"
            ") VALUES ("
            f"{area_sub}, {sql_bool(row['poder_sustitucion'])}, {estudiante_sub}, {estado_sub}, "
            f"{sql_str(row['estado_observacion'])}, {tipo_sub}, {sql_str(row['etapa_texto'])}, "
            f"{sql_date(row['etapa_fecha'])}"
            ");"
        )
    procesos += ["", "COMMIT;", ""]
    OUT_PROCESOS_MANUAL.write_text("\n".join(procesos), encoding="utf-8")

    print(f"wrote {OUT_CAT} bytes={OUT_CAT.stat().st_size}")
    print(f"wrote {OUT_HECHOS} bytes={OUT_HECHOS.stat().st_size}")
    print(f"wrote {OUT_PROCESOS_MANUAL} bytes={OUT_PROCESOS_MANUAL.stat().st_size} (carga MANUAL, no la corre el robot)")


if __name__ == "__main__":
    generar()
