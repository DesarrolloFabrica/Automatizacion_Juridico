-- Modelo del Consultorio Jurídico (Excel "CONTROL DE USUARIOS A-C.xlsx").
-- Esquema legal_consulting: YA EXISTE en la instancia CORE (creado previamente, vacío).
-- Este script es IDEMPOTENTE (CREATE ... IF NOT EXISTS) y solo agrega objetos dentro de
-- legal_consulting. No toca core, academic_workload, tickets ni ningún otro esquema.
--
-- Igual que en tickets: 0 FK físicas cross-schema. El cruce con core.person se resuelve
-- por aplicación (nombre normalizado), vía la columna core_person_id + match_status.
--
-- Fuente Excel: 2 hojas de grano distinto:
--   "CONTROL DE USUARIOS"  -> hecho consulta        (395 filas)
--   "PROCESOS 2025C"       -> hecho proceso_judicial (10 filas)

CREATE SCHEMA IF NOT EXISTS legal_consulting;

-- ---------------------------------------------------------------------------
-- Catálogos (viven en el Excel, no en CORE)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS legal_consulting.periodo_academico (
    id              smallserial PRIMARY KEY,
    codigo          varchar(10) NOT NULL UNIQUE,   -- ej. '2026A' (anio + letra_origen)
    letra_origen    varchar(5)  NOT NULL,           -- valor crudo de "# SEMESTRE" (A, C, ...)
    anio            smallint    NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_consulting.area_derecho (
    id          smallserial PRIMARY KEY,
    nombre      varchar(60) NOT NULL UNIQUE          -- PRIVADO, PUBLICO, LABORAL, CONCILIACION, PENAL...
);

CREATE TABLE IF NOT EXISTS legal_consulting.modalidad_atencion (
    id          smallserial PRIMARY KEY,
    nombre      varchar(40) NOT NULL UNIQUE          -- PRESENCIAL, VIRTUAL
);

CREATE TABLE IF NOT EXISTS legal_consulting.estado_caso (
    id          smallserial PRIMARY KEY,
    codigo      varchar(20) NOT NULL UNIQUE,         -- ABIERTO, CERRADO...
    nombre      varchar(40) NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_consulting.tipo_proceso (
    id                  smallserial PRIMARY KEY,
    nombre_normalizado  varchar(120) NOT NULL UNIQUE, -- typos de origen corregidos (ver normalizar_juridico.py)
    nombre_origen        varchar(120)                 -- primer valor crudo visto en el Excel, para trazabilidad
);

-- ---------------------------------------------------------------------------
-- Puente lógico a CORE (id CORE copiado si se resuelve, sin FK física)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS legal_consulting.estudiante_consultorio (
    id                      serial PRIMARY KEY,
    nombre_origen           varchar(200) NOT NULL,
    nombre_normalizado      varchar(200) NOT NULL UNIQUE,
    core_person_id          integer,                  -- lógico -> core.person.id (join por nombre, sin FK)
    match_status            varchar(20) NOT NULL DEFAULT 'pendiente'
        CHECK (match_status IN ('exacto', 'normalizado', 'pendiente', 'sin_match'))
);

-- ---------------------------------------------------------------------------
-- Hechos
-- ---------------------------------------------------------------------------

-- 1 fila = 1 atención/consulta registrada en "CONTROL DE USUARIOS".
-- ticket_externo NO es único: un mismo caso puede repetir varios motivos en la misma
-- fecha/hora (multi-motivo observado en origen); "NO REGISTRA" se guarda como NULL.
-- MODO ACUMULAR (piloto de automatización, sep 2026): como el Excel no trae un
-- identificador único de atención, se usa como llave natural la combinación de las 8
-- columnas de abajo (UNIQUE compuesta) -- si esa combinación exacta ya existe, la carga
-- la ignora (no duplica); si es nueva, la inserta. ticket_externo se guarda como texto
-- vacío ('') cuando no hay ticket (no NULL), para que la llave compuesta funcione bien
-- (NULL no es comparable consigo mismo en una restricción UNIQUE).
CREATE TABLE IF NOT EXISTS legal_consulting.consulta (
    id                  serial PRIMARY KEY,
    ticket_externo      varchar(20) NOT NULL DEFAULT '',
    fecha               date NOT NULL,
    hora_texto          varchar(20) NOT NULL DEFAULT '',
    periodo_id          smallint NOT NULL REFERENCES legal_consulting.periodo_academico (id),
    area_derecho_id     smallint NOT NULL REFERENCES legal_consulting.area_derecho (id),
    estudiante_id       integer  NOT NULL REFERENCES legal_consulting.estudiante_consultorio (id),
    modalidad_id        smallint NOT NULL REFERENCES legal_consulting.modalidad_atencion (id),
    estado_id           smallint NOT NULL REFERENCES legal_consulting.estado_caso (id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ticket_externo, fecha, hora_texto, area_derecho_id, estudiante_id, modalidad_id, estado_id)
);

-- 1 fila = 1 proceso judicial en curso, hoja "PROCESOS 2025C".
-- estado_observacion separa el texto adicional de valores compuestos como
-- "ABIERTO/ RENUNCIA DE PODER" (estado_id -> ABIERTO, observacion -> RENUNCIA DE PODER).
-- etapa_fecha queda NULL a propósito: el Excel trae etapas como texto libre sin año
-- ("AUDIENCIA 21 DE JULIO") y no es seguro inferir la fecha exacta; se deja para
-- completar manualmente cuando el dueño del dato la confirme.
CREATE TABLE IF NOT EXISTS legal_consulting.proceso_judicial (
    id                  serial PRIMARY KEY,
    area_derecho_id     smallint NOT NULL REFERENCES legal_consulting.area_derecho (id),
    poder_sustitucion   boolean,
    estudiante_id       integer  NOT NULL REFERENCES legal_consulting.estudiante_consultorio (id),
    estado_id           smallint NOT NULL REFERENCES legal_consulting.estado_caso (id),
    estado_observacion  varchar(200),
    tipo_proceso_id     smallint REFERENCES legal_consulting.tipo_proceso (id),
    etapa_texto         varchar(200),
    etapa_fecha         date,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_consulta_fecha ON legal_consulting.consulta (fecha);
CREATE INDEX IF NOT EXISTS ix_consulta_area ON legal_consulting.consulta (area_derecho_id);
CREATE INDEX IF NOT EXISTS ix_consulta_estudiante ON legal_consulting.consulta (estudiante_id);
CREATE INDEX IF NOT EXISTS ix_consulta_estado ON legal_consulting.consulta (estado_id);
CREATE INDEX IF NOT EXISTS ix_proceso_estudiante ON legal_consulting.proceso_judicial (estudiante_id);
CREATE INDEX IF NOT EXISTS ix_proceso_estado ON legal_consulting.proceso_judicial (estado_id);

-- Re-correr seguro si ya tenías el esquema cargado con la versión anterior (sin modo
-- acumular): agrega las columnas/restricción nuevas sin tocar las filas existentes.
ALTER TABLE legal_consulting.consulta ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'legal_consulting.consulta'::regclass
          AND conname = 'consulta_ticket_externo_fecha_hora_texto_area_derecho_id_e_key'
    ) THEN
        ALTER TABLE legal_consulting.consulta
            ADD CONSTRAINT consulta_ticket_externo_fecha_hora_texto_area_derecho_id_e_key
            UNIQUE (ticket_externo, fecha, hora_texto, area_derecho_id, estudiante_id, modalidad_id, estado_id);
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Seguimiento de archivos de Drive (piloto de automatización, sep 2026)
-- ---------------------------------------------------------------------------

-- 1 fila = 1 archivo de Drive que el robot ya procesó (ver automatizacion/sync_juridico.py).
-- Solo aplica a la hoja "CONTROL DE USUARIOS" (consulta): "PROCESOS" sigue cargándose a
-- mano (ver nota en legal_consulting.proceso_judicial más abajo), el robot no la toca.
CREATE TABLE IF NOT EXISTS legal_consulting.archivo_procesado (
    id                      serial PRIMARY KEY,
    drive_file_id           varchar(100) NOT NULL,
    nombre_archivo          varchar(300) NOT NULL,
    md5_checksum            varchar(64),
    procesado_en            timestamptz NOT NULL DEFAULT now(),
    consultas_en_archivo    integer,
    advertencias_totales    integer,
    advertencias_criticas   integer,
    estado                  varchar(20) NOT NULL
        CHECK (estado IN ('cargado', 'bloqueado_criticas', 'error')),
    detalle                 text,
    UNIQUE (drive_file_id, md5_checksum)
);

COMMENT ON TABLE legal_consulting.proceso_judicial IS
    'Procesos judiciales. NO tiene llave natural (el Excel de origen no trae número de '
    'expediente/radicado) -- por eso NO está en el modo acumular automático ni en el robot '
    'de Drive: se sigue cargando a mano (ver 03b_cargar_procesos_MANUAL.sql), revisando cada '
    'vez antes de correrlo. Ver Diccionario_Datos_Juridico.xlsx: ya se le pidió al Consultorio '
    'Jurídico agregar un número de expediente; el día que lo traigan, se puede automatizar.';

COMMENT ON SCHEMA legal_consulting IS
    'Consultorio Jurídico (consultas + procesos). Maestro de estudiante se resuelve contra CORE por nombre, sin FK física.';
COMMENT ON COLUMN legal_consulting.estudiante_consultorio.core_person_id IS
    'Join lógico: core.person.full_name normalizado. El Excel de Jurídico no trae documento de estudiante. Sin FK.';
COMMENT ON COLUMN legal_consulting.consulta.ticket_externo IS
    'Identificador del sistema de origen de Jurídico. No coincide con tickets.ticket.id_externo (Zarigüeya); sistemas distintos, no cruzar.';
