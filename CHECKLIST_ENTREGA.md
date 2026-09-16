# Checklist de entrega — Consultorio Jurídico

## A. Documentación

- [ ] `DOCUMENTACION_PROCESO.md`
- [ ] `DICCIONARIO_DATOS_EXCEL.md`
- [ ] `LEEME.txt`
- [ ] `automatizacion/DESPLIEGUE.md`
- [ ] README del repo enlaza los docs

## B. Piloto local (Fase 1)

- [ ] Dependencias instaladas
- [ ] `.env` desde `.env.example` (no en Git)
- [ ] Excel de prueba con hojas `CONTROL DE USUARIOS` y `PROCESOS …`
- [ ] `pipeline.py` genera SQL 02/03
- [ ] Carga local OK
- [ ] Revisar `advertencias_calidad.csv`

## C. Automatización nube (Fase 2)

- [ ] Cuenta de servicio **propia** de Jurídico + Drive compartido
- [ ] Secretos propios (no reutilizar los de Diplomados)
- [ ] Reutiliza IP/NAT/conector ya creados para Diplomados (no duplicar 1b)
- [ ] Cloud Run Job + Scheduler lunes ~9am
- [ ] Correo de aviso a destinatarios acordados
- [ ] Archivo ya procesado no se duplica

## D. Validación funcional

- [ ] Conteos de consultas / procesos coherentes con el Excel
- [ ] Catálogos poblados; muestra de estudiantes en puente CORE
- [ ] UPSERT sin duplicar en segunda corrida
- [ ] Esquema (`01_`) no se ejecuta en el Job diario

## E. Seguridad / repo

- [ ] Sin `.env` ni CSV con datos personales innecesarios en Git
- [ ] `.gitignore` correcto
- [ ] Producción solo autorizada

## Firma de cierre

| Campo | Valor |
|-------|-------|
| Fecha | |
| Responsable | |
| Observaciones | |
