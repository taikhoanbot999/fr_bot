#!/usr/bin/env bash
set -euo pipefail

# Rebuild all microservice Docker images and recreate containers
# Updated: use host bind mount for logs to allow cross-container + host sharing of transfer_status.json
# - Images: adlprocess, assetprocess, discord_shared_image
# - Containers: adlcontrol_container, assetcontrol_container, discord_shared_container
# - Host code root: /home/ubuntu/fr_bot/code
# - Shared logs host dir: /home/ubuntu/fr_bot/logs (bind mounted)
# - Adds TRANSFER_SHARE_DIR env var pointing to shared logs directory

# -------- Config --------
APP_ROOT="${APP_ROOT:-/home/ubuntu/fr_bot}"
CODE_DIR="${CODE_DIR:-$APP_ROOT/code}"
HOST_SETTINGS_DIR="${HOST_SETTINGS_DIR:-$CODE_DIR/_settings}"
HOST_LOGS_DIR="${HOST_LOGS_DIR:-$APP_ROOT/logs}"

IMAGE_ADL="${IMAGE_ADL:-adlprocess}"
IMAGE_ASSET="${IMAGE_ASSET:-assetprocess}"
IMAGE_DISCORD="${IMAGE_DISCORD:-discord_shared_image}"

CONTAINER_ADL="${CONTAINER_ADL:-adlcontrol_container}"
CONTAINER_ASSET="${CONTAINER_ASSET:-assetcontrol_container}"
CONTAINER_DISCORD="${CONTAINER_DISCORD:-discord_shared_container}"
# ------------------------

require_ubuntu() {
  if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    if [[ "${ID:-}" != "ubuntu" ]]; then
      echo "[ERROR] Detected: ${NAME:-unknown}. Please run on Ubuntu." >&2
      exit 1
    fi
  fi
}

install_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "[INFO] Installing Docker..."
    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg lsb-release
    sudo apt-get install -y docker.io docker-compose-plugin
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker "$USER" || true
  fi
}

ensure_host_logs_dir() {
  echo "[INFO] Ensuring host logs dir: $HOST_LOGS_DIR"
  sudo mkdir -p "$HOST_LOGS_DIR"
  sudo chown "$USER":"$USER" "$HOST_LOGS_DIR" || true
}

validate_paths() {
  [[ -d "$CODE_DIR" ]] || { echo "[ERROR] CODE_DIR not found: $CODE_DIR" >&2; exit 1; }
  [[ -d "$HOST_SETTINGS_DIR" ]] || { echo "[ERROR] HOST_SETTINGS_DIR not found: $HOST_SETTINGS_DIR" >&2; exit 1; }
}

build_images() {
  echo "[INFO] Rebuilding images from $CODE_DIR"
  sudo docker build -f "$CODE_DIR/MainProcess/ADLControl/Dockerfile" -t "$IMAGE_ADL" "$CODE_DIR"
  sudo docker build -f "$CODE_DIR/MainProcess/AssetControl/Dockerfile" -t "$IMAGE_ASSET" "$CODE_DIR"
  sudo docker build -f "$CODE_DIR/Notification/Dockerfile" -t "$IMAGE_DISCORD" "$CODE_DIR"
}

recreate_containers() {
  echo "[INFO] Removing old containers (ignore errors if not exist)"
  sudo docker rm -f "$CONTAINER_ADL" "$CONTAINER_ASSET" "$CONTAINER_DISCORD" 2>/dev/null || true

  echo "[INFO] Recreating containers (bind mount host logs; set TRANSFER_SHARE_DIR)"
  # ADL container (doesn't strictly need transfer share but keep consistency)
  sudo docker create --name "$CONTAINER_ADL" \
    -v "$HOST_LOGS_DIR":/home/ubuntu/fr_bot/logs \
    -v "$HOST_SETTINGS_DIR":/home/ubuntu/fr_bot/code/_settings \
    -e TRANSFER_SHARE_DIR=/home/ubuntu/fr_bot/logs \
    "$IMAGE_ADL"

  # Asset container (transfer logic lives here)
  sudo docker create --name "$CONTAINER_ASSET" \
    -v "$HOST_LOGS_DIR":/home/ubuntu/fr_bot/logs \
    -v "$HOST_SETTINGS_DIR":/home/ubuntu/fr_bot/code/_settings \
    -e TRANSFER_SHARE_DIR=/home/ubuntu/fr_bot/logs \
    "$IMAGE_ASSET"

  # Discord container
  sudo docker run -d --name "$CONTAINER_DISCORD" \
    --restart unless-stopped \
    -v "$HOST_LOGS_DIR":/home/ubuntu/fr_bot/logs \
    -v "$HOST_SETTINGS_DIR":/home/ubuntu/fr_bot/code/_settings \
    -e TRANSFER_SHARE_DIR=/home/ubuntu/fr_bot/logs \
    "$IMAGE_DISCORD"
}

post_checks() {
  echo "[INFO] Container status:"
  sudo docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
  echo "[INFO] Host logs dir contents (should include transfer_status.json after first transfer):"
  ls -l "$HOST_LOGS_DIR" || true
}

main() {
  echo "[INFO] Rebuild all microservice docker images & containers (bind mount logs)"
  require_ubuntu
  install_docker
  ensure_host_logs_dir
  validate_paths
  build_images
  recreate_containers
  post_checks
  echo "[DONE] Rebuild completed. Containers share host logs dir: $HOST_LOGS_DIR"
  echo "[INFO] Remember: systemd FastAPI server must also set TRANSFER_SHARE_DIR=$HOST_LOGS_DIR"
}

main "$@"
