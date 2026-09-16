# Documentación del proceso — Consultorio Jurídico

CUN · Fábrica de contenidos · sep 2026

Workflow completo: Excel de control de usuarios / procesos → Postgres (`esquema legal_consulting`) y robot automático (Fase 2).

Relacionado:

- `LEEME.txt` — piloto local (Fase 1)
- `automatizacion/DESPLIEGUE.md` — GCP (Fase 2)
- `CHECKLIST_ENTREGA.md`
- `DICCIONARIO_DATOS_EXCEL.md`

---

## 1. Qué problema resuelve

El Excel del Consultorio Jurídico trae **dos granos distintos**:

1. Atenciones / consultas (`CONTROL DE USUARIOS`)
2. Procesos judiciales (`PROCESOS …`)

El pipeline parte cada hoja en catálogos + hechos (`consulta`, `proceso_judicial`), sin inventar columnas (p. ej. no hay documento del consultante; se identifica al estudiante que atendió).

**No** es Diplomados ni el flujo LMS/Inventario. Repo independiente.

---

## 2. Fases

| Fase | Dónde | Qué es |
|------|--------|--------|
| **Fase 1 — Piloto** | PC (`pipeline.py`) | Normalizar y cargar a demanda |
| **Fase 2 — Automático** | GCP | Lunes ~9am revisa carpeta Drive de Jurídico |

Infra compartida con Diplomados (IP fija / NAT / conector VPC). Cuenta de servicio y secretos **propios** de Jurídico.

---

## 3. Workflow (flujo continuo)

### Fase 1

```
Excel .xlsx
  -> normalizar_juridico.py   (2 hojas)
  -> CSV
  -> generar_sql_carga.py
  -> 02_cargar_catalogos.sql + 03_cargar_juridico.sql
  -> (opcional) pipeline.py --cargar
```

### Fase 2

```
Cloud Scheduler
  -> Cloud Run Job
      -> sync_juridico.py
          Drive -> normalizar -> SQL -> UPSERT -> registro -> correo
```

Un solo job encadena los pasos. La creación del esquema (`01_...sql`) **no** forma parte del flujo diario.

---

## 4. Requisitos del Excel

Hojas esperadas:

- `CONTROL DE USUARIOS`
- `PROCESOS 2025C` (o nombre de periodo equivalente documentado en código)

Detalle: `DICCIONARIO_DATOS_EXCEL.md`

---

## 5. Base de datos

- Esquema: `legal_consulting`
- Modo acumular (UPSERT)
- `01_legal_consulting_schema.sql` solo para ambiente nuevo
- Match a CORE: por nombre de estudiante (no hay documento del consultante en el Excel)

---

## 6. Cómo correr (resumen)

```bash
pip install -r requirements.txt
copy .env.example .env

python normalizar_juridico.py "RUTA\CONTROL DE USUARIOS A-C.xlsx"
python pipeline.py "RUTA\CONTROL DE USUARIOS A-C.xlsx"
python pipeline.py "RUTA\CONTROL DE USUARIOS A-C.xlsx" --cargar
# Producción solo autorizada:
python pipeline.py "RUTA\....xlsx" --cargar --permitir-prod
```

Fase 2: `automatizacion/DESPLIEGUE.md`

---

## 7. Mapa de archivos clave

| Archivo | Rol |
|---------|-----|
| `normalizar_juridico.py` | Lee 2 hojas → CSV |
| `generar_sql_carga.py` | CSV → SQL |
| `pipeline.py` | Orquesta Fase 1 |
| `automatizacion/sync_juridico.py` | Orquesta Fase 2 |
| `01_legal_consulting_schema.sql` | Crear tablas (una vez) |
| `ERD_legal_consulting.html` | Diagrama |
