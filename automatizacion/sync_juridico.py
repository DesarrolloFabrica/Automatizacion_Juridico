"""
Orquestador de la Fase 2 (automatización) para Jurídico (Consultorio Jurídico).

Qué hace, en orden:
  1. Se conecta a Google Drive (cuenta de servicio) y lista los archivos de la carpeta
     de Jurídico en Drive (DRIVE_FOLDER_ID).
  2. Compara contra legal_consulting.archivo_procesado: si un archivo (por id + md5) ya
     se procesó antes, lo ignora. Si es nuevo o cambió su contenido, sigue.
  3. Para cada archivo nuevo: lo descarga, corre normalizar_juridico.normalizar() y
     generar_sql_carga.generar() (el MISMO código que ya está probado en
     pipeline_juridico/, sin duplicar lógica).
  4. Si hay advertencias "critico" (un dato sin el tipo esperado) -> NO carga nada a la
     base, deja el archivo marcado 'bloqueado_criticas' y lo dice en la notificación.
  5. Si no hay críticas -> ejecuta 02_cargar_catalogos.sql + 03_cargar_juridico.sql
     (UPSERT, modo acumular) contra Postgres.
     OJO: proceso_judicial (03b_cargar_procesos_MANUAL.sql) NUNCA lo ejecuta el robot --
     esa hoja no tiene llave natural en el Excel de origen (no trae número de
     expediente), así que sigue cargándose a mano. Ver LEEME.txt.
  6. Manda un correo con el resumen (a NOTIFY_EMAIL_TO) y registra cada archivo en
     legal_consulting.archivo_procesado.

Pensado para correr como Cloud Run Job, disparado por Cloud Scheduler cada lunes 9am
(hora Bogotá). Ver DESPLIEGUE.md para las variables de entorno y los comandos gcloud.

No toca core, academic_workload, diplomas, tickets, ni ningún otro esquema. Solo
legal_consulting, y solo consulta + catálogos (nunca proceso_judicial).
"""

from __future__ import annotations

import os
import smtplib
import sys
import tempfile
from email.mime.text import MIMEText
from pathlib import Path

import psycopg2
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# pipeline_juridico/ (carpeta padre) tiene normalizar_juridico.py y generar_sql_carga.py;
# se reutilizan tal cual, sin copiar ni reescribir su lógica.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from normalizar_juridico import normalizar  # noqa: E402
import generar_sql_carga as generador  # noqa: E402

DRIVE_FOLDER_ID = os.environ["DRIVE_FOLDER_ID"]
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


# ---------------------------------------------------------------------------
# Drive
# ---------------------------------------------------------------------------

def get_drive_service():
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path:
        creds = service_account.Credentials.from_service_account_file(cred_path, scopes=DRIVE_SCOPES)
        return build("drive", "v3", credentials=creds)
    # En Cloud Run sin variable explícita, usa las credenciales del propio servicio (ADC)
    # -- requiere que la cuenta de servicio del Cloud Run Job tenga acceso de lectura a
    # la carpeta de Drive (compartida explícitamente con su email, ver DESPLIEGUE.md).
    return build("drive", "v3")


def listar_archivos(drive) -> list[dict]:
    resp = drive.files().list(
        q=f"'{DRIVE_FOLDER_ID}' in parents and trashed = false",
        fields="files(id, name, md5Checksum, modifiedTime)",
        orderBy="modifiedTime",
    ).execute()
    return resp.get("files", [])


def descargar_archivo(drive, file_id: str, destino: Path) -> None:
    request = drive.files().get_media(fileId=file_id)
    with destino.open("wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


# ---------------------------------------------------------------------------
# Postgres
# ---------------------------------------------------------------------------

def conectar_db():
    # Misma conexión directa por IP pública que Diplomados (mismo core-database, mismo
    # conector VPC + Cloud NAT ya autorizados) -- ver automatizacion/DESPLIEGUE.md.
    return psycopg2.connect(
        host=os.environ.get("LEGAL_DB_HOST", "localhost"),
        port=os.environ.get("LEGAL_DB_PORT", "5432"),
        dbname=os.environ["LEGAL_DB_NAME"],
        user=os.environ["LEGAL_DB_USER"],
        password=os.environ["LEGAL_DB_PASSWORD"],
        sslmode="require",
    )


def archivos_ya_procesados(conn) -> set[tuple[str, str | None]]:
    with conn.cursor() as cur:
        cur.execute("SELECT drive_file_id, md5_checksum FROM legal_consulting.archivo_procesado;")
        return {(r[0], r[1]) for r in cur.fetchall()}


def registrar(conn, archivo: dict, stats: dict, estado: str, detalle: str = "") -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO legal_consulting.archivo_procesado
                (drive_file_id, nombre_archivo, md5_checksum, consultas_en_archivo,
                 advertencias_totales, advertencias_criticas, estado, detalle)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                archivo["id"], archivo["name"], archivo.get("md5Checksum"),
                stats.get("consultas"), stats.get("advertencias"),
                stats.get("advertencias_criticas", 0), estado, detalle,
            ),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Notificación
# ---------------------------------------------------------------------------

def notificar(asunto: str, cuerpo: str) -> None:
    # NOTIFY_EMAIL_TO admite uno o varios correos separados por coma.
    to_raw = os.environ.get("NOTIFY_EMAIL_TO")
    to_addrs = [addr.strip() for addr in to_raw.split(",")] if to_raw else []
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    if not to_addrs or not smtp_user or not smtp_password:
        print("Notificación por correo no configurada (falta NOTIFY_EMAIL_TO/SMTP_USER/"
              "SMTP_PASSWORD); se omite el envío. Resumen:\n" + cuerpo)
        return
    msg = MIMEText(cuerpo)
    msg["Subject"] = asunto
    msg["From"] = smtp_user
    msg["To"] = ", ".join(to_addrs)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_password)
        server.sendmail(msg["From"], to_addrs, msg.as_string())


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

def procesar_archivo(drive, conn, archivo: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        ruta_excel = tmp / archivo["name"]
        descargar_archivo(drive, archivo["id"], ruta_excel)

        salida = tmp / "salida"
        stats = normalizar(ruta_excel, salida)
        generador.generar(base_dir=salida)

        if stats.get("advertencias_criticas", 0):
            registrar(conn, archivo, stats, "bloqueado_criticas")
            return {"estado": "bloqueado_criticas", "archivo": archivo["name"], **stats}

        with conn.cursor() as cur:
            # OJO: NO se ejecuta 03b_cargar_procesos_MANUAL.sql -- proceso_judicial
            # sigue cargándose a mano (ver LEEME.txt).
            cur.execute((salida / "02_cargar_catalogos.sql").read_text(encoding="utf-8"))
            cur.execute((salida / "03_cargar_juridico.sql").read_text(encoding="utf-8"))
        conn.commit()

        registrar(conn, archivo, stats, "cargado")
        return {"estado": "cargado", "archivo": archivo["name"], **stats}


def main() -> None:
    drive = get_drive_service()
    conn = conectar_db()

    ya_procesados = archivos_ya_procesados(conn)
    candidatos = listar_archivos(drive)
    nuevos = [a for a in candidatos if (a["id"], a.get("md5Checksum")) not in ya_procesados]

    if not nuevos:
        print(f"Sin archivos nuevos en la carpeta de Drive ({len(candidatos)} revisados, todos ya procesados).")
        conn.close()
        return

    resultados = []
    for archivo in nuevos:
        try:
            resultados.append(procesar_archivo(drive, conn, archivo))
        except Exception as exc:  # noqa: BLE001 -- se quiere capturar cualquier falla y notificar, no tumbar el job
            conn.rollback()
            registrar(conn, archivo, {}, "error", str(exc))
            resultados.append({"estado": "error", "archivo": archivo["name"], "detalle": str(exc)})

    conn.close()

    lineas = [f"Jurídico — revisión automática de Drive ({len(nuevos)} archivo(s) nuevo(s)):", ""]
    for r in resultados:
        if r["estado"] == "cargado":
            lineas.append(
                f"✅ {r['archivo']}: {r.get('consultas')} consultas cargadas "
                f"({r.get('advertencias', 0)} advertencias, ninguna crítica). "
                "Procesos judiciales NO se tocaron (siguen a mano)."
            )
        elif r["estado"] == "bloqueado_criticas":
            lineas.append(
                f"🚫 {r['archivo']}: BLOQUEADO, no se cargó nada — "
                f"{r.get('advertencias_criticas')} advertencia(s) crítica(s) (dato sin el tipo "
                "esperado). Revisar el archivo y volver a subirlo corregido."
            )
        else:
            lineas.append(f"⚠️ {r['archivo']}: error inesperado — {r.get('detalle')}")
    cuerpo = "\n".join(lineas)

    print(cuerpo)
    notificar("Jurídico — carga automática semanal", cuerpo)


if __name__ == "__main__":
    main()
