-- Solo lectura. No modifica nada. Cruza legal_consulting.estudiante_consultorio
-- contra core.person por nombre normalizado (sin tildes, mayúsculas, espacios
-- colapsados) — el Excel de Jurídico no trae documento de estudiante, así que
-- el único cruce posible es por nombre.
--
-- No asume la extensión unaccent (puede no estar instalada); usa translate()
-- para las tildes/ñ más comunes del español, que sí es función nativa.

-- 1) Estudiantes con match EXACTO de nombre en core.person (candidatos fuertes)
SELECT
    ec.id                AS estudiante_id,
    ec.nombre_normalizado,
    cp.id                AS core_person_id,
    cp.full_name         AS core_full_name,
    cp.document          AS core_document,
    cp.email             AS core_email,
    cp.program_id        AS core_program_id
FROM legal_consulting.estudiante_consultorio ec
JOIN core.person cp
  ON UPPER(regexp_replace(
       translate(trim(cp.full_name), 'áéíóúÁÉÍÓÚñÑüÜ', 'aeiouAEIOUnNuU'),
       '\s+', ' ', 'g'
     )) = ec.nombre_normalizado
ORDER BY ec.id;

-- 2) Estudiantes SIN match exacto (para revisar a mano: puede ser que el nombre
--    en core.person esté en otro orden, con más/menos nombres, o la persona no
--    sea estudiante activo en core en este momento).
SELECT ec.id, ec.nombre_normalizado
FROM legal_consulting.estudiante_consultorio ec
WHERE NOT EXISTS (
    SELECT 1
    FROM core.person cp
    WHERE UPPER(regexp_replace(
            translate(trim(cp.full_name), 'áéíóúÁÉÍÓÚñÑüÜ', 'aeiouAEIOUnNuU'),
            '\s+', ' ', 'g'
          )) = ec.nombre_normalizado
)
ORDER BY ec.id;

-- 3) Match por CONJUNTO de palabras (sin importar el orden). core.person.full_name
--    puede guardar "APELLIDOS NOMBRES" mientras el Excel trae "NOMBRES APELLIDOS";
--    esta consulta compara las mismas palabras sin exigir el mismo orden.
--    Documentado en el PDF de CORE: academic_workload.student "corresponde_a"
--    core.person vía person_id (UNIQUE uq_student_person, sin FK física).
SELECT
    ec.id                AS estudiante_id,
    ec.nombre_normalizado,
    cp.id                AS core_person_id,
    cp.full_name         AS core_full_name,
    cp.document          AS core_document,
    cp.email             AS core_email
FROM legal_consulting.estudiante_consultorio ec
JOIN core.person cp
  ON (
        SELECT array_agg(w ORDER BY w)
        FROM unnest(string_to_array(ec.nombre_normalizado, ' ')) AS w
     )
  = (
        SELECT array_agg(w ORDER BY w)
        FROM unnest(string_to_array(
               UPPER(regexp_replace(
                 translate(trim(cp.full_name), 'áéíóúÁÉÍÓÚñÑüÜ', 'aeiouAEIOUnNuU'),
                 '\s+', ' ', 'g'
               )), ' '
             )) AS w
     )
ORDER BY ec.id;
