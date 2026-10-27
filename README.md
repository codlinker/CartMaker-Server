# 🛒 CartMaker Backend - Guía de Instalación, Configuración y Monitoreo

Este repositorio contiene el núcleo lógico de CartMaker, incluyendo el sistema de autenticación biométrica basado en vectores, la gestión de tareas asíncronas y la infraestructura de telemetría en tiempo real.

## 📋 Requisitos del Sistema
* **OS:** `Ubuntu` (WSL local o servidor EC2)
* **Python:** `3.14.3`
* **Base de Datos:** PostgreSQL con extensiones `pgvector` y `postgis`.
* **Broker & Caché:** Redis Server (Obligatorio para tareas asíncronas y el sistema Split Caching).
* **Servidor ASGI:** Uvicorn.
* **Telemetría:** Prometheus, Grafana y PostgreSQL Exporter.

## 🔐 Archivos Requeridos (Solicitar al Administrador)
Debes colocar estos archivos en la ruta raíz del proyecto:
1. `firebase-adminsdk.json`: Credenciales de administración para Firebase.
2. `variables.sh`: Script con las variables de entorno necesarias.

---

## 🛠️ Instrucciones de Instalación

### 1. Preparación del Entorno
Desde la ruta raíz del proyecto, ejecuta:

```bash
# Actualizar el entorno de ubuntu
sudo apt update && sudo apt upgrade -y

# Instalar postgresql y dependencias de compilación
sudo apt install -y postgresql postgresql-contrib build-essential postgresql-server-dev-all

# Instalar pgvector
cd /tmp
git clone --branch v0.8.2 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Instalar postgis
sudo apt install -y postgresql-18-postgis-3

# Volver al directorio de tu proyecto
cd /ruta/a/tu/proyecto

# Crear el entorno virtual (Asegurar Python 3.14.3)
python3.14 -m venv venv

# Activar el entorno
source venv/bin/activate

# Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# Asegurar la instalación de los componentes de escalabilidad
pip install celery redis uvicorn django-silk

```

### 2. Configuración de Infraestructura (Redis y Node)

```bash
sudo apt update
sudo apt install redis-server -y

# Iniciar y habilitar para que arranque automáticamente con el sistema
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Verificar conexión (Debe responder PONG)
redis-cli ping

# Instlar Node JS (Necesario para los websockets)
sudo apt install nodejs

```

### 3. Migraciones a la Base de Datos

```bash
# No hace falta activar las variables de entorno porque el código
# las busca automáticamente del archivo variables.sh en la carpeta base.
source venv/bin/activate
python3 manage.py migrate

```

---

## 📊 Configuración de Monitoreo (PostgreSQL Exporter + Prometheus + Grafana) OPCIONAL - OMITIR

Este sistema permite monitorear el consumo de CPU, memoria, transacciones por segundo (TPS) y bloqueos de PostgreSQL.

### A. Crear Usuario de Monitoreo en Postgres

Ingresa a la consola de administración de Postgres:

```bash
sudo -u postgres psql

```

Ejecuta los siguientes comandos SQL:

```sql
CREATE USER exporter WITH PASSWORD 'tu_password_seguro';
GRANT pg_monitor TO exporter;
\q

```

### B. Instalar y Configurar PostgreSQL Exporter

Descarga el binario y configúralo como un servicio para que corra en segundo plano:

```bash
# Descargar y extraer
cd /tmp
wget [https://github.com/prometheus-community/postgres_exporter/releases/download/v0.15.0/postgres_exporter-0.15.0.linux-amd64.tar.gz](https://github.com/prometheus-community/postgres_exporter/releases/download/v0.15.0/postgres_exporter-0.15.0.linux-amd64.tar.gz)
tar -xvf postgres_exporter-0.15.0.linux-amd64.tar.gz

# Mover el binario a una ruta del sistema
sudo mv postgres_exporter-0.15.0.linux-amd64/postgres_exporter /usr/local/bin/

```

Crea el servicio de Systemd:

```bash
sudo nano /etc/systemd/system/postgres_exporter.service

```

Pega el siguiente contenido (reemplaza `cartmaker_local` por el nombre de tu BD):

```ini
[Unit]
Description=Prometheus PostgreSQL Exporter
After=network.target

[Service]
User=ubuntu
Environment=DATA_SOURCE_NAME="postgresql://exporter:tu_password_seguro@localhost:5432/cartmaker_local?sslmode=disable"
ExecStart=/usr/local/bin/postgres_exporter
Restart=always

[Install]
WantedBy=multi-user.target

```

Inicia y habilita el servicio:

```bash
sudo systemctl daemon-reload
sudo systemctl start postgres_exporter
sudo systemctl enable postgres_exporter

```

### C. Instalar y Configurar Prometheus

```bash
sudo apt install prometheus -y

```

Edita la configuración para indicarle que lea las métricas del Exporter:

```bash
sudo nano /etc/prometheus/prometheus.yml

```

Añade esto al final del archivo dentro de la sección `scrape_configs`:

```yaml
  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']

```

Reinicia el servicio para aplicar los cambios:

```bash
sudo systemctl restart prometheus
sudo systemctl enable prometheus

```

### D. Instalar y Configurar Grafana

Añade el repositorio oficial e instala Grafana:

```bash
sudo apt-get install -y apt-transport-https software-properties-common wget
sudo mkdir -p /etc/apt/keyrings
wget -q -O - [https://apt.grafana.com/gpg.key](https://apt.grafana.com/gpg.key) | gpg --dearmor | sudo tee /etc/apt/keyrings/grafana.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] [https://apt.grafana.com](https://apt.grafana.com) stable main" | sudo tee /etc/apt/sources.list.d/grafana.list

sudo apt-get update
sudo apt-get install grafana -y

```

Inicia y habilita el servicio:

```bash
sudo systemctl start grafana-server
sudo systemctl enable grafana-server

```

### E. Conectar el Dashboard en la Interfaz Web

1. Abre tu navegador en `http://localhost:3000`.
2. Inicia sesión con **Usuario:** `admin` | **Contraseña:** `admin`.
3. Ve a **Connections > Data Sources > Add data source** y elige **Prometheus**.
4. En el campo **URL** escribe: `http://localhost:9090` y dale a **Save & Test**.
5. Ve a **Dashboards > New > Import**.
6. Escribe el ID **9628**, haz clic en Load, selecciona tu base de datos Prometheus y dale a **Import**.

---

## 🚀 Ejecución y Servicios del Proyecto

CartMaker-Server está compuesto por **4 servicios principales de aplicación** (más `postgresql` y `redis-server`):

| Servicio (`systemd`) | Puerto interno | Rol principal |
| :--- | :--- | :--- |
| **`cartmaker-backend`** | `8000` | Servidor ASGI (`uvicorn`) de Django: API REST `/api/v1/`, panel administrativo y páginas legales (`/privacidad/`, `/eliminar-cuenta/`). |
| **`cartmaker-celery`** | — | Worker asíncrono + planificador periódico (`celery worker -B`): generación de miniaturas WebP (`thumb`/`medium`), moderación IA de imágenes/videos, transcodificación de historias (`imageio-ffmpeg` / MediaConvert), correos OTP/facturas, alertas Push FCM, ofertas de delivery y volcado de analíticas. |
| **`cartmaker-chat`** | `3001` | Microservicio Node.js (`node_chat_server/index.js`) con Socket.IO y adaptador Redis: chat de órdenes y soporte tripartito, eventos `order_updated` en tiempo real y telemetría GPS de repartidores. |
| **`cartmaker-osrm`** *(alias de `osrm-car`)* | `127.0.0.1:5000` | Motor de ruteo vial C++ nativo (`osrm-routed --mmap`) con el mapa de Venezuela para cotización de distancias, tiempos de entrega y polilíneas de delivery. |

---

### A. Gestión de Servicios en Producción (EC2 con `systemd`)

#### Comandos de uso diario
```bash
# Reiniciar TODOS los servicios de CartMaker tras un despliegue
sudo systemctl restart cartmaker-backend cartmaker-celery cartmaker-chat cartmaker-osrm

# Verificar el estado de todos los servicios de un vistazo
sudo systemctl status cartmaker-backend cartmaker-celery cartmaker-chat cartmaker-osrm

# Iniciar o detener todos los servicios
sudo systemctl start cartmaker-backend cartmaker-celery cartmaker-chat cartmaker-osrm
sudo systemctl stop cartmaker-backend cartmaker-celery cartmaker-chat cartmaker-osrm

# Habilitar arranque automático al reiniciar la EC2
sudo systemctl enable cartmaker-backend cartmaker-celery cartmaker-chat cartmaker-osrm redis-server postgresql
```

#### Consultar logs en vivo (`journalctl`)
```bash
# Logs en tiempo real por servicio
sudo journalctl -u cartmaker-backend -f
sudo journalctl -u cartmaker-celery -f
sudo journalctl -u cartmaker-chat -f
sudo journalctl -u cartmaker-osrm -f

# Ver las últimas 100 líneas de todos los servicios juntos
sudo journalctl -u cartmaker-backend -u cartmaker-celery -u cartmaker-chat -u cartmaker-osrm -n 100 --no-pager
```

---

### B. Checklist de Despliegue / Actualización en EC2 (`git pull`)

Cada vez que subas cambios a `main` y actualices el servidor en EC2, ejecuta en orden:

```bash
cd ~/CartMaker-Server

# 1. Descargar últimos cambios del repositorio
git pull

# 2. Activar el entorno virtual e instalar/actualizar dependencias Python
#    (incluye imageio-ffmpeg==0.6.0 con el binario estático de ffmpeg precompilado)
source venv/bin/activate
pip install -r requirements.txt

# 3. Aplicar migraciones de base de datos y recolectar archivos estáticos
python manage.py migrate
python manage.py collectstatic --noinput

# 4. (Opcional pero recomendado) Sincronizar catálogo base, categorías y SystemConfig
python manage.py fill_default_bd

# 5. Si hubo cambios en node_chat_server/package.json
cd node_chat_server && npm install --omit=dev && cd ..

# 6. Reiniciar los servicios para cargar el nuevo código y las tareas de Celery
sudo systemctl restart cartmaker-backend cartmaker-celery cartmaker-chat cartmaker-osrm
```

---

### C. Comandos de Mantenimiento y Backfill (`manage.py` y `scripts/`)

Todos estos comandos se ejecutan con el entorno virtual activo (`source venv/bin/activate`):

#### 1. Backfill de variantes de imagen (`thumb` 320 px / `medium` 800 px en WebP) y `Cache-Control`
Las imágenes **nuevas** que se suben a la app generan automáticamente sus miniaturas `.webp` en segundo plano mediante Celery y se guardan con `Cache-Control: public, max-age=31536000, immutable`.  
Para rellenar las imágenes **antiguas** que ya existían antes de esta actualización, existe el comando idempotente `backfill_image_variants` (puedes interrumpirlo y volverlo a correr: salta automáticamente lo que ya esté listo):

```bash
# 1) Ver cuántas imágenes existen y cuántas faltan por generar (no modifica nada)
python manage.py backfill_image_variants --dry-run

# 2) Ejecutar el backfill completo + actualizar cabeceras Cache-Control en S3 (recomendado correr 1 vez)
python manage.py backfill_image_variants --cache-control --workers 4

# Opciones avanzadas por si deseas correrlo por partes:
python manage.py backfill_image_variants --only products combos --limit 500 --workers 4
python manage.py backfill_image_variants --force   # Regenera variantes aunque ya existan
```

#### 2. Poblado y sincronización de datos base (`fill_default_bd`)
Sincroniza sin duplicar las categorías, subcategorías, esquemas de atributos/tallas, tarifas de `SystemConfig`, planes y centros comerciales:
```bash
python manage.py fill_default_bd
```

#### 3. Instalación / actualización del motor vial OSRM (`cartmaker-osrm`)
Descarga los binarios nativos de OSRM v5.27.1 en `/opt/osrm/rootfs`, descarga y verifica por MD5 el mapa vial de Venezuela desde Geofabrik, compila el grafo MLD (creando `/swapfile` automático si la EC2 tiene poca RAM) e instala/reinicia el servicio `osrm-car` (con alias `cartmaker-osrm`) en `127.0.0.1:5000`:
```bash
bash scripts/osrm/rebuild.sh

# Para forzar recompilación aunque el mapa .pbf no haya cambiado:
FORCE=1 bash scripts/osrm/rebuild.sh
```

#### 4. Migración de documentos sensibles a bucket privado S3 (`migrate_private_s3`)
Normaliza rutas heredadas y copia documentos privados (KYC/KYB, capturas de pago, adjuntos de chat) al bucket privado con cifrado `AES256`:
```bash
python manage.py migrate_private_s3 --dry-run
python manage.py migrate_private_s3 --delete-from-public
```

#### 5. Calibración de umbrales biométricos (`calibrate_biometric_thresholds.py`)
Calcula FAR, FRR, EER y umbrales recomendados `1:1` y `1:N` a partir de un archivo CSV/JSONL de pares de embeddings (`mobilefacenet-fp32-v1` o `mobilefacenet-int8-v1`):
```bash
python scripts/calibrate_biometric_thresholds.py --self-test
python scripts/calibrate_biometric_thresholds.py --input pares.jsonl --model-version mobilefacenet-int8-v1
```

---

### D. Tareas Periódicas Automáticas (ejecutadas por `cartmaker-celery`)

Al correr `celery` con la bandera `-B` (Beat integrado), el servicio `cartmaker-celery` ejecuta automáticamente:
- **Cada 30 segundos:** `expire_and_retry_delivery_offers_task` (expira ofertas de delivery tras 45 s sin respuesta y reintenta asignación).
- **Cada 15 minutos:** `process_analytics_batch` (vuelca las colas Redis de vistas de productos, tiendas, navegación, video engagement y demanda insatisfecha hacia PostgreSQL).
- **Cada hora (minuto 0):** `cleanup_expired_video_stories` (limpia archivos de video/miniatura de historias vencidas tras 72 h).
- **Cada 6 horas:** `send_uncompleted_orders_reminders_to_merchants` (recordatorio a comercios con órdenes abiertas > 6 h).
- **Diario 12:02 AM:** `cleanup_expired_offers` (elimina ofertas caducadas e invalida caché zonal).
- **Diario 03:00 AM:** `evaluate_platinum_status` (evalúa métricas y otorga/revoca estatus Platinum).
- **Diario 03:30 AM:** `cleanup_expired_delivery_traces_task` (elimina trazas GPS con > 30 días por Habeas Data).
- **Diario 03:45 AM:** `cleanup_old_notifications` (poda notificaciones leídas > 30 días o > 30 por usuario y no leídas > 90 días).
- **Diario 10:00 AM:** `notify_atlas_plus_expiring` (envía aviso Push FCM a suscriptores Atlas Plus que vencen en ≤ 3 días).
- **Diario 08:00 PM:** `refresh_admin_dashboard_metrics` (actualiza tasa BCV y precalcula métricas financieras del dashboard).

---

### E. Ejecución Manual en Desarrollo Local (Terminales separadas)

Si estás desarrollando localmente sin `systemd`, abre las siguientes terminales en la raíz del proyecto (con `source venv/bin/activate`):

#### Terminal 1 — Servidor de la API (Uvicorn)
```bash
uvicorn cartmaker_admin.asgi:application --host 0.0.0.0 --port 8000 --reload
```

#### Terminal 2 — Worker + Beat de Celery
```bash
celery -A cartmaker_admin worker -B --loglevel=info --concurrency=2
```

#### Terminal 3 — Microservicio de Chat y Tiempo Real (Node.js)
```bash
node node_chat_server/index.js
```

#### Terminal 4 — Motor de rutas OSRM (Opcional en local; si no corre, usa fallback Haversine)
```bash
bash scripts/osrm/rebuild.sh
```

> **Nota:** Si agregas o modificas tareas en `api/tasks.py` o `api/core/image_variants.py`, recuerda reiniciar `cartmaker-celery` (`sudo systemctl restart cartmaker-celery`) para que los workers carguen el código nuevo.
