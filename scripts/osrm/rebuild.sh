#!/usr/bin/env bash
# =============================================================================
# Reconstruye los datos de OSRM a partir del extracto de Venezuela de Geofabrik
# y levanta osrm-routed como servicio nativo de Linux (systemd).
#
# - Instalación nativa: descarga los binarios C++ precompilados de OSRM v5.27.1
#   directo a /opt/osrm/rootfs usando solo curl + python3 + tar.
# - Modo --mmap activo por defecto: osrm-routed mapea el grafo desde disco sin
#   cargar todo en RAM (~80-120 MB de consumo real).
# - Idempotente: si el .pbf no cambió y los datos ya existen, no reprocesa (FORCE=1 para forzar).
# - Algoritmo MLD: osrm-extract -> osrm-partition -> osrm-customize.
#
# Variables opcionales:
#   OSRM_ROOTFS    (por defecto: /opt/osrm/rootfs)
#   OSRM_PBF_URL   (por defecto: https://download.geofabrik.de/south-america/venezuela-latest.osm.pbf)
#   OSRM_TAG       (por defecto: v5.27.1)
#   BUILD_BIKE=1   (compila y levanta también el perfil bicycle en puerto 5001)
#   FORCE=1        (reprocesa aunque el .pbf no haya cambiado)
#   SKIP_RESTART=1 (no reinicia el servicio systemd al terminar)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOTFS="${OSRM_ROOTFS:-/opt/osrm/rootfs}"
DATA_DIR="$ROOTFS/data"
PBF_URL="${OSRM_PBF_URL:-https://download.geofabrik.de/south-america/venezuela-latest.osm.pbf}"
OSRM_TAG="${OSRM_TAG:-v5.27.1}"
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

for bin in curl python3 tar md5sum flock; do
  command -v "$bin" >/dev/null 2>&1 || { log "ERROR: falta el comando '$bin'."; exit 1; }
done

# -----------------------------------------------------------------------------
# 0. Protección para instancias AWS EC2 Micro (1 GB RAM): asegura Swap >= 2.8 GB
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

# -----------------------------------------------------------------------------
# 1. Descarga de binarios precompilados de OSRM en /opt/osrm/rootfs
# -----------------------------------------------------------------------------
ensure_osrm_rootfs() {
  if [ -x "$ROOTFS/usr/local/bin/osrm-routed" ] || [ -x "$ROOTFS/usr/bin/osrm-routed" ]; then
    log "Binarios nativos de OSRM ya presentes en $ROOTFS."
    return 0
  fi

  log "Descargando binarios precompilados de OSRM ($OSRM_TAG) directamente..."
  sudo mkdir -p "$ROOTFS"
  local tmp_layers
  tmp_layers="$(mktemp -d)"

  python3 - "$OSRM_TAG" "$tmp_layers" <<'PYEOF'
import json
import platform
import subprocess
import sys
import urllib.request

tag = sys.argv[1]
tmp_dir = sys.argv[2]
repo = "project-osrm/osrm-backend"

# 1. Obtener token anónimo de lectura de GHCR
token_url = f"https://ghcr.io/token?service=ghcr.io&scope=repository:{repo}:pull"
with urllib.request.urlopen(token_url, timeout=30) as resp:
    token = json.loads(resp.read().decode())["token"]

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": (
        "application/vnd.oci.image.index.v1+json, "
        "application/vnd.docker.distribution.manifest.list.v2+json, "
        "application/vnd.oci.image.manifest.v1+json, "
        "application/vnd.docker.distribution.manifest.v2+json"
    ),
}

def fetch_manifest(ref):
    req = urllib.request.Request(f"https://ghcr.io/v2/{repo}/manifests/{ref}", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

manifest = fetch_manifest(tag)
if "manifests" in manifest:
    arch = "arm64" if platform.machine() in ("aarch64", "arm64") else "amd64"
    chosen = None
    for m in manifest["manifests"]:
        plat = m.get("platform", {})
        if plat.get("os") == "linux" and plat.get("architecture") == arch:
            chosen = m["digest"]
            break
    if not chosen:
        chosen = manifest["manifests"][0]["digest"]
    manifest = fetch_manifest(chosen)

layers = manifest.get("layers", [])
for idx, layer in enumerate(layers, 1):
    digest = layer["digest"]
    out_file = f"{tmp_dir}/layer_{idx}.tar.gz"
    blob_url = f"https://ghcr.io/v2/{repo}/blobs/{digest}"
    print(f"[osrm-rebuild] Descargando capa {idx}/{len(layers)} ({digest[:19]}...)...", flush=True)
    subprocess.run(
        ["curl", "-fsSL", "--retry", "3", "-H", f"Authorization: Bearer {token}", "-o", out_file, blob_url],
        check=True,
    )
PYEOF

  for layer_tar in "$tmp_layers"/layer_*.tar.gz; do
    sudo tar --overwrite -xzf "$layer_tar" -C "$ROOTFS" 2>/dev/null || sudo tar -xzf "$layer_tar" -C "$ROOTFS"
  done
  rm -rf "$tmp_layers"

  # Limpia archivos whiteout de capas OCI si existen
  sudo find "$ROOTFS" -name '.wh.*' -delete 2>/dev/null || true

  if [ ! -x "$ROOTFS/usr/local/bin/osrm-routed" ] && [ ! -x "$ROOTFS/usr/bin/osrm-routed" ]; then
    log "ERROR: No se encontró osrm-routed tras extraer las capas en $ROOTFS."
    exit 1
  fi
  log "Binarios OSRM instalados correctamente en $ROOTFS."
}

ensure_osrm_rootfs

sudo mkdir -p "$DATA_DIR"
sudo chown -R "$(id -u):$(id -g)" "$DATA_DIR"

# Crea enlace simbólico en scripts/osrm/data -> /opt/osrm/rootfs/data para fácil inspección
if [ ! -e "$SCRIPT_DIR/data" ]; then
  ln -s "$DATA_DIR" "$SCRIPT_DIR/data" 2>/dev/null || true
fi

# Evita dos reconstrucciones simultáneas
exec 9>"$DATA_DIR/.rebuild.lock"
if ! flock -n 9; then
  log "Ya hay una reconstrucción en curso. Saliendo."
  exit 0
fi

# -----------------------------------------------------------------------------
# 2. Descarga del extracto (solo si cambió en Geofabrik) + verificación MD5
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
# 3. Preprocesado MLD por perfil ejecutando el binario nativo en chroot
# -----------------------------------------------------------------------------
cleanup_chroot_mounts() {
  sudo umount -l "$ROOTFS/proc" 2>/dev/null || true
  sudo umount -l "$ROOTFS/sys" 2>/dev/null || true
  sudo umount -l "$ROOTFS/dev" 2>/dev/null || true
}
trap cleanup_chroot_mounts EXIT

prepare_chroot_mounts() {
  sudo mkdir -p "$ROOTFS/proc" "$ROOTFS/sys" "$ROOTFS/dev"
  mountpoint -q "$ROOTFS/proc" || sudo mount -t proc proc "$ROOTFS/proc"
  mountpoint -q "$ROOTFS/sys"  || sudo mount -t sysfs sys "$ROOTFS/sys"
  mountpoint -q "$ROOTFS/dev"  || sudo mount --bind /dev "$ROOTFS/dev"
}

osrm_run() {
  prepare_chroot_mounts
  sudo chroot "$ROOTFS" /usr/bin/env PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin "$@"
}

CHANGED=0
THREADS="$(nproc 2>/dev/null || echo 1)"

for profile in "${PROFILES[@]}"; do
  target="$DATA_DIR/$profile"
  marker="$target/.source.md5"

  if [ "$FORCE" != "1" ] && [ -f "$marker" ] && [ "$(cat "$marker")" = "$SOURCE_MD5" ] && [ -f "$target/$OSRM_NAME.partition" ]; then
    log "[$profile] Datos al día. Se omite."
    continue
  fi

  stage="$DATA_DIR/$profile.new"
  chroot_stage="/data/$profile.new"
  sudo rm -rf "$stage"
  mkdir -p "$stage"
  ln "$PBF_PATH" "$stage/$PBF_NAME" 2>/dev/null || cp "$PBF_PATH" "$stage/$PBF_NAME"

  log "[$profile] osrm-extract (threads=$THREADS)..."
  osrm_run osrm-extract -t "$THREADS" -p "/opt/$profile.lua" "$chroot_stage/$PBF_NAME"
  log "[$profile] osrm-partition (threads=$THREADS)..."
  osrm_run osrm-partition -t "$THREADS" "$chroot_stage/$OSRM_NAME"
  log "[$profile] osrm-customize (threads=$THREADS)..."
  osrm_run osrm-customize -t "$THREADS" "$chroot_stage/$OSRM_NAME"

  sudo rm -f "$stage/$PBF_NAME"
  sudo chown -R "$(id -u):$(id -g)" "$stage"
  echo "$SOURCE_MD5" > "$stage/.source.md5"

  sudo rm -rf "$DATA_DIR/$profile.old"
  if [ -d "$target" ]; then
    sudo mv "$target" "$DATA_DIR/$profile.old"
  fi
  sudo mv "$stage" "$target"
  sudo rm -rf "$DATA_DIR/$profile.old"
  CHANGED=1
  log "[$profile] Listo."
done

# Desmontamos /proc, /sys, /dev antes de iniciar los servicios systemd con RootDirectory=
cleanup_chroot_mounts

# -----------------------------------------------------------------------------
# 4. Instalación y arranque del servicio nativo systemd
# -----------------------------------------------------------------------------
if [ -x "$ROOTFS/usr/local/bin/osrm-routed" ]; then
  OSRM_ROUTED_BIN="/usr/local/bin/osrm-routed"
else
  OSRM_ROUTED_BIN="/usr/bin/osrm-routed"
fi

install_systemd_unit() {
  local svc_name="$1"
  local profile="$2"
  local port="$3"
  local unit_path="/etc/systemd/system/${svc_name}.service"

  sudo tee "$unit_path" >/dev/null <<EOF
[Unit]
Description=CartMaker OSRM Routing Engine (${profile}, --mmap, Native)
After=network.target

[Service]
Type=simple
RootDirectory=${ROOTFS}
ExecStart=${OSRM_ROUTED_BIN} --algorithm mld --mmap --max-table-size 100 --ip 127.0.0.1 --port ${port} /data/${profile}/${OSRM_NAME}
Restart=always
RestartSec=3
MemoryMax=350M

[Install]
WantedBy=multi-user.target
Alias=cartmaker-osrm.service
EOF
  if [ "$svc_name" = "osrm-car" ]; then
    sudo ln -sf "$unit_path" /etc/systemd/system/cartmaker-osrm.service
  fi
}

if [ "$SKIP_RESTART" = "1" ]; then
  log "SKIP_RESTART=1: no se reinician los servicios systemd."
else
  log "Configurando servicio nativo systemd (osrm-car.service en 127.0.0.1:5000)..."
  install_systemd_unit "osrm-car" "car" "5000"
  if [ "$BUILD_BIKE" = "1" ]; then
    install_systemd_unit "osrm-bike" "bicycle" "5001"
  fi
  sudo systemctl daemon-reload
  sudo systemctl enable osrm-car.service >/dev/null 2>&1 || true
  sudo systemctl restart osrm-car.service

  if [ "$BUILD_BIKE" = "1" ]; then
    sudo systemctl enable osrm-bike.service >/dev/null 2>&1 || true
    sudo systemctl restart osrm-bike.service
  fi

  sleep 2
  if curl -fsS "http://127.0.0.1:5000/route/v1/driving/-66.9036,10.4806;-66.8520,10.4910?overview=false" >/dev/null 2>&1; then
    log "EXITO: OSRM nativo respondiendo en http://127.0.0.1:5000 (modo --mmap)."
  else
    log "AVISO: El servicio osrm-car se inició; verifica su estado con: sudo systemctl status osrm-car"
  fi
fi

log "Terminado."
