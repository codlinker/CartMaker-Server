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
git clone --branch v0.8.2 [https://github.com/pgvector/pgvector.git](https://github.com/pgvector/pgvector.git)
cd pgvector
make
sudo make install

# Instalar postgis
sudo apt install -y postgresql-16-postgis-3

# Volver al directorio de tu proyecto
# cd /ruta/a/tu/proyecto

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

### 2. Configuración de Infraestructura (Redis)

```bash
sudo apt update
sudo apt install redis-server -y

# Iniciar y habilitar para que arranque automáticamente con el sistema
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Verificar conexión (Debe responder PONG)
redis-cli ping

```

### 3. Migraciones a la Base de Datos

```bash
# No hace falta activar las variables de entorno porque el código
# las busca automáticamente del archivo variables.sh en la carpeta base.
source venv/bin/activate
python3 manage.py migrate

```

---

## 📊 Configuración de Monitoreo (PostgreSQL Exporter + Prometheus + Grafana)

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

## 🚀 Ejecución del Proyecto

Se deben tener estas 3 terminales abiertas:

### Terminal 1 - Servidor de la API (Uvicorn)

```bash
uvicorn cartmaker_admin.asgi:application --host 0.0.0.0 --port 8000 --reload

```

### Terminal 2: Worker de Celery

Este proceso ejecuta todas las tasks en segundo plano, evitando que acciones pesadas bloqueen la velocidad de respuesta del servidor.

```bash
celery -A cartmaker_admin worker -B --loglevel=info --concurrency=2 

```

### Terminal 3: Microservicio de Chat

Este proceso ejecuta el microservicio de Node.js para el manejo de Websockets para las conversaciones
en tiempo real en los chats de las ordenes activas (chat de compra y venta).

```bash
node  node_chat_server/index.js

```


> **Nota:** Si agregas nuevas funciones a `tasks.py`, recuerda reiniciar el proceso de Celery para que las reconozca.
> EOF

```