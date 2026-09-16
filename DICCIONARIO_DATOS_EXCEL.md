# Diccionario de datos — Excel Consultorio Jurídico

Fuente tipica: `CONTROL DE USUARIOS A-C.xlsx` (o equivalente del periodo).

## Hojas del libro

| Hoja | Grano | Destino |
|------|-------|---------|
| `CONTROL DE USUARIOS` | 1 fila = 1 atención/consulta | hecho `consulta` + catálogos |
| `PROCESOS 2025C` | 1 fila = 1 proceso judicial | hecho `proceso_judicial` + catálogos |

Ambas hojas son obligatorias para el normalizador.

## Columnas requeridas — CONTROL DE USUARIOS

| Columna Excel | Significado |
|---------------|-------------|
| `FECHA` | Fecha de la atención |
| `HORA` | Hora de la atención |
| `TICKET` | Identificador de ticket (puede venir vacío / "NO REGISTRA") |
| `# SEMESTRE` | Semestre del estudiante |
| `MOTIVO DE CONSULTA` | Motivo / área temática de la consulta |
| `ESTUDIANTE ASIGNADO` | Nombre del estudiante del consultorio que atendió |
| `MODALIDAD` | Modalidad de atención |
| `ESTADO` | Estado de la consulta/caso |

## Columnas requeridas — PROCESOS

| Columna Excel | Significado |
|---------------|-------------|
| `LINEA` | Línea / área del proceso |
| `PODER DE SUSTITUCION` | Indicador de poder de sustitución |
| `ESTUDIANTE ASIGNADO` | Estudiante a cargo |
| `ESTADO` | Estado del proceso |
| `TIPO` | Tipo de proceso (con corrección de typos conocidos en código) |
| `ETAPA` | Etapa procesal |

### Typos de `TIPO` que el código corrige

| Valor origen (mal escrito) | Valor canónico |
|----------------------------|----------------|
| EJECUTVO SINGULAR | EJECUTIVO SINGULAR |
| EJECUTIVO DE ALIMENTOAS | EJECUTIVO DE ALIMENTOS |
| PROCESO DICIPLINARIO | PROCESO DISCIPLINARIO |
| DECLARTIVO DE FAMILIA | DECLARATIVO DE FAMILIA |

## Destino en base (`esquema legal_consulting`)

| Concepto | Uso |
|----------|-----|
| Catálogos | área_derecho, periodo, estado, tipo_proceso, modalidad, etc. |
| Puente CORE | `estudiante_consultorio` (por nombre; el Excel no trae doc del consultante) |
| Hechos | `consulta`, `proceso_judicial` |

## Nota

No hay documento de identidad del usuario/consultante en este Excel: el cruce con CORE es por el **estudiante asignado**, no por el ciudadano atendido.
