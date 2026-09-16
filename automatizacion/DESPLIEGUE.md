# Despliegue de la automatización de Jurídico (Fase 2)

Esto convierte el pipeline ya validado (carpeta `pipeline_juridico/`, modo acumular) en un
proceso que corre solo cada lunes 9am, revisando la carpeta de Jurídico en Drive.

**Buena noticia: la parte pesada de infraestructura YA EXISTE** (se construyó para
Diplomados y es reutilizable tal cual): la IP fija (`diplomados-nat-ip`), el conector VPC
(`diplomados-connector`), el router + Cloud NAT, y la entrada en "redes autorizadas" de
`core-database`. NO hay que repetir el paso 1b de la guía de Diplomados.

Sí se crea una cuenta de servicio y unos secretos NUEVOS y separados para Jurídico
(principio de mínimo privilegio: si algo pasa con el robot de Jurídico, no afecta al de
Diplomados, y viceversa).

## Valores ya conocidos (reusados de Diplomados)

| Dato | Valor |
|---|---|
| Proyecto | `it-fab-contenido-edu-6` |
| Región | `us-central1` |
| Conector VPC (compartido) | `diplomados-connector` |
| IP pública de `core-database` | `136.113.128.135` |
| Carpeta Drive de Jurídico | `11Llp4ACR_F2I9j4Gyaoy0xGysYK_yZPz` |
| Correo de aviso | `angie_vera@cun.edu.co,sara_martinezl@cun.edu.co` (varios, separados por coma) |
| Remitente del correo | `fabricadecontenidos@cun.edu.co` (misma cuenta que Diplomados) |

```powershell
$PROJECT_ID   = "it-fab-contenido-edu-6"
$REGION       = "us-central1"
$DRIVE_FOLDER_ID = "11Llp4ACR_F2I9j4Gyaoy0xGysYK_yZPz"
$NOTIFY_TO    = "angie_vera@cun.edu.co,sara_martinezl@cun.edu.co"
$DB_HOST      = "136.113.128.135"
```

(En Cloud Shell, que usa bash, se ponen igual pero sin `$` al final de cada nombre, ej.
`PROJECT_ID=it-fab-contenido-edu-6`.)

## 1. Crear la cuenta de servicio del robot de Jurídico

```bash
gcloud iam service-accounts create juridico-sync \
    --display-name="Jurídico - sync automático Drive -> legal_consulting"
```

Compartir la carpeta de Drive de Jurídico con
`juridico-sync@$PROJECT_ID.iam.gserviceaccount.com` como "Lector" (igual que se hizo con
Diplomados).

## 2. Guardar los secretos (contraseña de BD + correo)

Usa `read -s VAR` + `printf '%s' "$VAR" | gcloud secrets create ...` -- **NUNCA** `echo`
(le pega un salto de línea invisible al final que rompe la contraseña; ya nos pasó una
vez con Diplomados).

```bash
read -s DB_PASSWORD
printf '%s' "$DB_PASSWORD" | gcloud secrets create juridico-db-password --data-file=-

read -s SMTP_PASSWORD
printf '%s' "$SMTP_PASSWORD" | gcloud secrets create juridico-smtp-password --data-file=-

gcloud secrets add-iam-policy-binding juridico-db-password \
    --member="serviceAccount:juridico-sync@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding juridico-smtp-password \
    --member="serviceAccount:juridico-sync@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

La contraseña de BD es la del mismo usuario que ya usa Diplomados (confirmar con
pgAdmin antes, igual que se hizo la vez pasada). La contraseña de SMTP es la misma
"contraseña de aplicación" ya generada para `fabricadecontenidos@cun.edu.co` (se puede
copiar el mismo valor, o generar una nueva app password específica para este robot --
cualquiera de las dos funciona).

## 3. Construir la imagen (desde `pipeline_juridico/`, OJO con el contexto)

```bash
cd ~/pipeline_juridico
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/juridico/sync:latest"
gcloud artifacts repositories create juridico --repository-format=docker --location=$REGION
gcloud builds submit --config=automatizacion/cloudbuild.yaml --substitutions=_IMAGE=$IMAGE .
```

## 4. Crear el Cloud Run Job (reusa el conector VPC ya existente)

```bash
gcloud run jobs create juridico-sync \
    --image=$IMAGE \
    --region=$REGION \
    --service-account="juridico-sync@$PROJECT_ID.iam.gserviceaccount.com" \
    --vpc-connector=diplomados-connector \
    --vpc-egress=all-traffic \
    --set-env-vars="^;^DRIVE_FOLDER_ID=$DRIVE_FOLDER_ID;LEGAL_DB_HOST=$DB_HOST;LEGAL_DB_NAME=core;LEGAL_DB_USER=user-core;NOTIFY_EMAIL_TO=$NOTIFY_TO;SMTP_USER=fabricadecontenidos@cun.edu.co" \
    --set-secrets="LEGAL_DB_PASSWORD=juridico-db-password:latest,SMTP_PASSWORD=juridico-smtp-password:latest" \
    --max-retries=1 \
    --task-timeout=900
```

Nota: `--set-env-vars="^;^..."` usa `;` como separador en vez de `,` porque
`$NOTIFY_TO` ya trae una coma adentro (varios correos) -- si se usara `,` como
separador normal, `gcloud` lo confundiría con el separador de variables.

`LEGAL_DB_NAME=core` es intencional (Jurídico también vive en la base compartida
`core`, dentro del esquema `legal_consulting`).

## 5. Crear el disparador (Cloud Scheduler, cada lunes 9am hora Bogotá)

```bash
gcloud scheduler jobs create http juridico-sync-semanal \
    --location=$REGION \
    --schedule="0 9 * * 1" \
    --time-zone="America/Bogota" \
    --uri="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/juridico-sync:run" \
    --http-method=POST \
    --oauth-service-account-email="juridico-sync@$PROJECT_ID.iam.gserviceaccount.com"
```

## 6. Probarlo ya, sin esperar al lunes

```bash
gcloud run jobs execute juridico-sync --region=$REGION
gcloud run jobs executions list --job=juridico-sync --region=$REGION
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=juridico-sync" --limit=50 --format="value(textPayload)" --freshness=10m
```

## Qué revisar la primera vez

1. Confirma que la carpeta de Drive de Jurídico esté compartida con
   `juridico-sync@$PROJECT_ID.iam.gserviceaccount.com` como Lector.
2. Corre el paso 6 (ejecución manual).
3. Debe llegar un correo a `angie_vera@cun.edu.co` y `sara_martinezl@cun.edu.co` diciendo
   cuántas consultas se cargaron.
4. Verifica en pgAdmin:
   `SELECT * FROM legal_consulting.archivo_procesado ORDER BY procesado_en DESC;`
5. Vuelve a correr el paso 6 sin cambiar nada en Drive: debe decir "sin archivos nuevos".
6. Recuerda: `proceso_judicial` (los procesos judiciales) NUNCA los toca este robot --
   siguen cargándose a mano con `03b_cargar_procesos_MANUAL.sql`, revisando cada vez.
