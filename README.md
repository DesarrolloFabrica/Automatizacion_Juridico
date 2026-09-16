# Automatización Consultorio Jurídico

Pipeline CUN · Fábrica de contenidos: Excel de control de usuarios / procesos → Postgres (`esquema legal_consulting`), con robot semanal en GCP.

## Qué es (y qué no es)

| Esto sí | Esto no |
|---------|---------|
| Consultas y procesos del consultorio | Diplomados (repo aparte) |
| Robot lunes Drive → BD | Flujo LMS / Inventario |
| Esquema `legal_consulting` | Pendientes Cruce CORE |

## Docs (empieza aquí)

1. [DOCUMENTACION_PROCESO.md](DOCUMENTACION_PROCESO.md)  
2. [DICCIONARIO_DATOS_EXCEL.md](DICCIONARIO_DATOS_EXCEL.md)  
3. [CHECKLIST_ENTREGA.md](CHECKLIST_ENTREGA.md)  
4. [LEEME.txt](LEEME.txt)  
5. [automatizacion/DESPLIEGUE.md](automatizacion/DESPLIEGUE.md)  

## Uso rápido (local)

```bash
pip install -r requirements.txt
copy .env.example .env

python pipeline.py "RUTA\CONTROL DE USUARIOS A-C.xlsx"
python pipeline.py "RUTA\CONTROL DE USUARIOS A-C.xlsx" --cargar
```

Hojas obligatorias: `CONTROL DE USUARIOS` y `PROCESOS 2025C` (o periodo equivalente).

## Estructura

```
pipeline_juridico/
  normalizar_juridico.py
  generar_sql_carga.py
  pipeline.py
  01_legal_consulting_schema.sql
  automatizacion/
    sync_juridico.py
    DESPLIEGUE.md
    Dockerfile
  DOCUMENTACION_PROCESO.md
  DICCIONARIO_DATOS_EXCEL.md
  CHECKLIST_ENTREGA.md
```

## Requisitos

- Python 3.10+
- Postgres local para pruebas
- GCP para Fase 2 (comparte red con Diplomados; secretos separados)
