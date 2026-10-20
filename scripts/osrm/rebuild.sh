#!/usr/bin/env bash
# =============================================================================
# Reconstruye los datos de OSRM (car + bicycle) a partir del extracto de Venezuela
# de Geofabrik y reinicia los contenedores. Pensado para correr a mano o por cron/Celery Beat.
#
# - Idempotente: si el .pbf no cambió y los datos ya existen, no reprocesa (FORCE=1 para forzar).
# - Construye en un directorio temporal y hace el intercambio al final: si algo falla,
#   los datos anteriores siguen intactos y los contenedores siguen sirviendo.
# - Algoritmo MLD: osrm-extract -> osrm-partition -> osrm-customize.
#
# Variables opcionales:
#   OSRM_DATA_DIR  (por defecto: scripts/osrm/data)
#   OSRM_PBF_URL   (por defecto: https://download.geofabrik.de/south-america/venezuela-latest.osm.pbf)
#   OSRM_IMAGE     (por defecto: ghcr.io/project-osrm/osrm-backend:v5.27.1)
#   FORCE=1        (reprocesa aunque el .pbf no haya cambiado)
#   SKIP_RESTART=1 (no reinicia los contenedores al terminar)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${OSRM_DATA_DIR:-$SCRIPT_DIR/data}"
PBF_URL="${OSRM_PBF_URL:-https://download.geofabrik.de/south-america/venezuela-latest.osm.pbf}"
IMAGE="${OSRM_IMAGE:-ghcr.io/project-osrm/osrm-backend:v5.27.1}"
PBF_NAME="venezuela-latest.osm.pbf"
OSRM_NAME="venezuela-latest.osrm"
BUILD_BIKE="${BUILD_BIKE:-0}"
if [ "$BUILD_BIKE" = "1" ]; then
  PROFILES=("car" "bicycle")
else
  PROFILES=("car")
fi
FORCE="${FORCE:-0}"
SKIP_RESTART="${SKIP_RESTART:-0}"
AUTO_SWAP="${AUTO_SWAP:-1}"

log() { echo "[osrm-rebuild $(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# -----------------------------------------------------------------------------
# 0. Protección para instancias AWS EC2 Micro (1 GB RAM): asegura Swap >= 2.5 GB
# -----------------------------------------------------------------------------
ensure_swap_for_micro() {
  if [ ! -f /proc/meminfo ]; then
    return 0
  fi
  local mem_kb swap_kb total_mb
  mem_kb="$(awk '/MemTotal:/ {print $2}' /proc/meminfo)"
  swap_kb="$(awk '/SwapTotal:/ {print $2}' /proc/meminfo)"
  total_mb=$(( (mem_kb + swap_kb) / 1024 ))

  if [ "$total_mb" -ge 2800 ]; then
    log "Memoria disponible (RAM + Swap): ${total_mb} MB (suficiente para compilar)."
    return 0
  fi

  log "Instancia con poca memoria detectada (RAM + Swap = ${total_mb} MB)."
  if [ "$AUTO_SWAP" = "1" ] && [ ! -f /swapfile ]; then
    log "Creando archivo /swapfile de 4 GB en disco para evitar que osrm-extract agote la RAM..."
    if sudo fallocate -l 4G /swapfile 2>/dev/null || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096 status=none; then
      sudo chmod 600 /swapfile
      sudo mkswap /swapfile >/dev/null
      sudo swapon /swapfile
      if ! grep -q '/swapfile' /etc/fstab 2>/dev/null; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
      fi
      log "Swap de 4 GB activado correctamente."
    else
      log "AVISO: No se pudo crear /swapfile automáticamente. Asegúrate de tener sudo o al menos 3 GB de RAM+Swap."
    fi
  fi
}

ensure_swap_for_micro

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose -f "$SCRIPT_DIR/docker-compose.yml" "$@"
  else
    docker-compose -f "$SCRIPT_DIR/docker-compose.yml" "$@"
  fi
}

for bin in docker curl md5sum flock; do
  command -v "$bin" >/dev/null 2>&1 || { log "ERROR: falta el comando '$bin'."; exit 1; }
done

mkdir -p "$DATA_DIR"

# Evita dos reconstrucciones simultáneas
exec 9>"$DATA_DIR/.rebuild.lock"
if ! flock -n 9; then
  log "Ya hay una reconstrucción en curso. Saliendo."
  exit 0
fi

# -----------------------------------------------------------------------------
# 1. Descarga del extracto (solo si cambió en Geofabrik) + verificación MD5
# -----------------------------------------------------------------------------
PBF_PATH="$DATA_DIR/$PBF_NAME"
TMP_PBF="$DATA_DIR/$PBF_NAME.download"
TMP_MD5="$DATA_DIR/$PBF_NAME.md5.download"
rm -f "$TMP_PBF" "$TMP_MD5"

log "Descargando $PBF_URL (si hay una versión nueva)..."
if [ -f "$PBF_PATH" ]; then
  curl -fsSL --retry 3 --retry-delay 5 -z "$PBF_PATH" -o "$TMP_PBF" "$PBF_URL"
else
  curl -fsSL --retry 3 --retry-delay 5 -o "$TMP_PBF" "$PBF_URL"
fi

if [ -s "$TMP_PBF" ]; then
  log "Verificando MD5..."
  curl -fsSL --retry 3 --retry-delay 5 -o "$TMP_MD5" "$PBF_URL.md5"
  expected_md5="$(awk '{print $1}' "$TMP_MD5")"
  actual_md5="$(md5sum "$TMP_PBF" | awk '{print $1}')"
  if [ "$expected_md5" != "$actual_md5" ]; then
    log "ERROR: MD5 no coincide (esperado $expected_md5, obtenido $actual_md5)."
    rm -f "$TMP_PBF" "$TMP_MD5"
    exit 1
  fi
  mv -f "$TMP_PBF" "$PBF_PATH"
  log "Extracto actualizado."
else
  log "El extracto no cambió."
fi
rm -f "$TMP_PBF" "$TMP_MD5"

if [ ! -s "$PBF_PATH" ]; then
  log "ERROR: no existe $PBF_PATH."
  exit 1
fi
SOURCE_MD5="$(md5sum "$PBF_PATH" | awk '{print $1}')"

# -----------------------------------------------------------------------------
# 2. Preprocesado MLD por perfil (en staging + intercambio atómico)
# -----------------------------------------------------------------------------
osrm_run() {
  local workdir="$1"
  shift
  docker run --rm --user "$(id -u):$(id -g)" -v "$workdir:/data" "$IMAGE" "$@"
}

CHANGED=0
for profile in "${PROFILES[@]}"; do
  target="$DATA_DIR/$profile"
  marker="$target/.source.md5"

  if [ "$FORCE" != "1" ] && [ -f "$marker" ] && [ "$(cat "$marker")" = "$SOURCE_MD5" ] && [ -f "$target/$OSRM_NAME.partition" ]; then
    log "[$profile] Datos al día. Se omite."
    continue
  fi

  stage="$DATA_DIR/$profile.new"
  rm -rf "$stage"
  mkdir -p "$stage"
  # Enlace duro si es posible (no duplica espacio); si no, copia
  ln "$PBF_PATH" "$stage/$PBF_NAME" 2>/dev/null || cp "$PBF_PATH" "$stage/$PBF_NAME"

  log "[$profile] osrm-extract..."
  osrm_run "$stage" osrm-extract -p "/opt/$profile.lua" "/data/$PBF_NAME"
  log "[$profile] osrm-partition..."
  osrm_run "$stage" osrm-partition "/data/$OSRM_NAME"
  log "[$profile] osrm-customize..."
  osrm_run "$stage" osrm-customize "/data/$OSRM_NAME"

  rm -f "$stage/$PBF_NAME"
  echo "$SOURCE_MD5" > "$stage/.source.md5"

  rm -rf "$DATA_DIR/$profile.old"
  if [ -d "$target" ]; then
    mv "$target" "$DATA_DIR/$profile.old"
  fi
  mv "$stage" "$target"
  rm -rf "$DATA_DIR/$profile.old"
  CHANGED=1
  log "[$profile] Listo."
done

# -----------------------------------------------------------------------------
# 3. Reinicio de los contenedores
# -----------------------------------------------------------------------------
if [ "$SKIP_RESTART" = "1" ]; then
  log "SKIP_RESTART=1: no se reinician los contenedores."
elif [ "$CHANGED" = "1" ]; then
  log "Reiniciando contenedores OSRM..."
  compose up -d --force-recreate
else
  log "Sin cambios: se asegura que los contenedores estén arriba."
  compose up -d
fi

log "Terminado."
