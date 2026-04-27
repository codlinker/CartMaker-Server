# 🛒 CartMaker Backend - Guía de Instalación y Configuración

Este repositorio contiene el núcleo lógico de CartMaker, incluyendo el sistema de autenticación biométrica basado en vectores y la gestión de tareas asíncronas.

## 📋 Requisitos del Sistema
* **OS:** `Ubuntu`
* **Python:** `3.14`
* **Base de Datos:** PostgreSQL con extensión `pgvector`.
* **Broker:** Redis Server (Obligatorio para tareas asíncronas).
* **Uvicorn:** Para ejecutar el proyecto en su servidor ASGI.

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
sudo apt update

# Instalar postgresql
sudo apt install postgresql postgresql-contrib

# Actualizar repositorio de dependencias de pgvector
sudo apt install build-essential postgresql-server-dev-all

# Instalar pgvector
cd /tmp
git clone --branch v0.8.2 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Instalar postgis
sudo apt install postgresql-16-postgis-3

# Crear el entorno virtual
python3.14 -m venv venv

# Activar el entorno
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
# Asegurar la instalación de los componentes de escalabilidad
pip install celery redis

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

### 3. Migraciones a la base de datos

```bash
# No hace falta activar las variables de entorno porque el codigo
# las busca automaticamente del archivo variables.sh en la carpeta
# base del proyecto.
python3 manage.py migrate
```

## 🚀 Ejecución del Proyecto (Modo Desarrollo)

Se deben tener estas 2 terminales abiertas:

### Terminal 1 - Servidor de la app.

```bash
uvicorn cartmaker_admin.asgi:application --host 0.0.0.0 --port 8000 --reload
# Tambien se puede ejecutar en el host 0.0.0.0 en caso de que se este
# trabajando con un emulador de la app en Flutter y el backend a la vez
# en local.
```

### Terminal 2: Worker de Celery

Este proceso ejecuta todas las tasks en segundo plano. Es el que evita
que acciones pesadas bloqueen la velocidad de respuesta del servidor,
mejorando la UX.

```bash
celery -A cartmaker_admin worker --loglevel=info --concurrency=2 # 2 o cantidad de nucleos a utilizar del procesador.
```

> **Nota:** Si agregas nuevas funciones a `tasks.py`, recuerda reiniciar el proceso de Celery para que las reconozca.