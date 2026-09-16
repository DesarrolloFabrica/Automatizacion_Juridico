<div align="center">

# Automatización Consultorio Jurídico

**CUN · Fábrica de contenidos** — Excel de consultas/procesos → Postgres (`legal_consulting`) + robot semanal en GCP

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-legal__consulting-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Run%20%2B%20Scheduler-4285F4?logo=googlecloud&logoColor=white)](https://cloud.google.com/)
[![Drive](https://img.shields.io/badge/Google%20Drive-fuente%20Excel-0F9D58?logo=googledrive&logoColor=white)](https://drive.google.com/)
[![Licencia](https://img.shields.io/badge/Uso-interno%20CUN-orange)](#)

</div>

---

## Tabla de contenido

- [Visión general](#-visión-general)
- [Documentación](#-documentación)
- [Uso rápido (local)](#-uso-rápido-local)
- [Flujo continuo](#-flujo-continuo)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Requisitos](#-requisitos)

---

## Visión general

Pipeline del **Consultorio Jurídico**: lee el Excel de control de usuarios (consultas) y procesos judiciales, normaliza catálogos + hechos y carga en modo **acumular** (UPSERT).

| Fase | Dónde | Qué hace |
|------|--------|----------|
| **Fase 1** | PC | Piloto / prueba con `pipeline.py` |
| **Fase 2** | GCP | Robot cada lunes ~9am (`sync_juridico.py`) |

Hojas obligatorias: **`CONTROL DE USUARIOS`** y **`PROCESOS 2025C`** (o periodo equivalente).

---

## Documentación

| Doc | Para qué |
|-----|----------|
| [DOCUMENTACION_PROCESO.md](DOCUMENTACION_PROCESO.md) | Workflow paso a paso |
| [DICCIONARIO_DATOS_EXCEL.md](DICCIONARIO_DATOS_EXCEL.md) | Hojas y columnas |
| [CHECKLIST_ENTREGA.md](CHECKLIST_ENTREGA.md) | Validar entrega |
| [automatizacion/DESPLIEGUE.md](automatizacion/DESPLIEGUE.md) | Comandos GCP (Fase 2) |

---

## Uso rápido (local)

```bash
pip install -r requirements.txt
copy .env.example .env

python pipeline.py "RUTA\CONTROL DE USUARIOS A-C.xlsx"
python pipeline.py "RUTA\CONTROL DE USUARIOS A-C.xlsx" --cargar
```

Producción solo autorizada. El `01_legal_consulting_schema.sql` **no** va en el flujo diario.

---

## Flujo continuo

```
Excel → normalizar (2 hojas) → generar SQL → (cargar) → registrar / correo
```

- Local: `pipeline.py`
- Nube: `automatizacion/sync_juridico.py`

Comparte red GCP con Diplomados; **secretos y cuenta de servicio propios**.

---

## Estructura del proyecto

```
Automatizacion_Juridico/
├── README.md
├── DOCUMENTACION_PROCESO.md
├── DICCIONARIO_DATOS_EXCEL.md
├── CHECKLIST_ENTREGA.md
├── normalizar_juridico.py
├── generar_sql_carga.py
├── pipeline.py
├── 01_legal_consulting_schema.sql
├── 04a_verificar_match_core_person.sql
├── requirements.txt
├── .env.example
└── automatizacion/
    ├── sync_juridico.py
    ├── DESPLIEGUE.md
    ├── Dockerfile
    └── cloudbuild.yaml
```

---

## Requisitos

- Python 3.10+
- PostgreSQL local para pruebas
- Fase 2: GCP (Run + Scheduler + Drive + Secret Manager)
