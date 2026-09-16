# Imagen del Cloud Run Job que corre sync_juridico.py cada lunes 9am (disparado por
# Cloud Scheduler). Copia el pipeline completo (pipeline_juridico/) porque
# sync_juridico.py reutiliza normalizar_juridico.py y generar_sql_carga.py tal cual.

FROM python:3.12-slim

WORKDIR /app

# 1) dependencias propias de la automatización (Drive API, etc.)
COPY automatizacion/requirements.txt ./requirements-automatizacion.txt
RUN pip install --no-cache-dir -r requirements-automatizacion.txt

# 2) el pipeline ya probado (normalizar_juridico.py, generar_sql_carga.py, etc.)
COPY normalizar_juridico.py generar_sql_carga.py ./

# 3) el orquestador
COPY automatizacion/sync_juridico.py ./automatizacion/sync_juridico.py

ENTRYPOINT ["python", "automatizacion/sync_juridico.py"]
