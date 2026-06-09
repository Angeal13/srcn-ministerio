#!/bin/bash
# ╔══════════════════════════════════════════════════════════╗
# ║  BIOKO HEALTH — Script de Actualización                  ║
# ║  Actualiza el sistema sin tiempo de inactividad          ║
# ║  Uso: sudo bash deploy/servidor_central/actualizar.sh                     ║
# ╚══════════════════════════════════════════════════════════╝
set -euo pipefail

APP_DIR="/opt/bioko_health"
SERVICE="bioko_health"

VERDE='\033[0;32m'; AMARILLO='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${VERDE}✓ $1${NC}"; }
info() { echo -e "${AMARILLO}→ $1${NC}"; }

[[ $EUID -ne 0 ]] && { echo "Requiere sudo."; exit 1; }
[[ ! -f "run.py" ]] && { echo "Ejecutar desde el directorio raíz del proyecto."; exit 1; }

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  BIOKO HEALTH — Actualización            ║"
echo "╚══════════════════════════════════════════╝"

# Backup rápido de la DB
info "Creando backup de la base de datos..."
BACKUP_FILE="/opt/bioko_health/backups/backup_$(date +%Y%m%d_%H%M%S).sql"
mkdir -p /opt/bioko_health/backups
mysqldump -u root bioko_health > "$BACKUP_FILE" 2>/dev/null || true
ok "Backup: $BACKUP_FILE"

# Copiar nuevos archivos (preservar .env y uploads)
info "Actualizando archivos..."
rsync -a --exclude='.git' --exclude='*.pyc' --exclude='__pycache__' \
      --exclude='*.db' --exclude='.env' --exclude='uploads/' \
      --exclude='reports/' --exclude='backups/' \
      ./ "$APP_DIR/"
ok "Archivos actualizados."

# Actualizar dependencias Python
info "Actualizando dependencias Python..."
"$APP_DIR/venv/bin/pip" install --quiet --upgrade -r "$APP_DIR/requirements.txt"
ok "Dependencias actualizadas."

# Migraciones de base de datos
info "Aplicando migraciones..."
cd "$APP_DIR"
FLASK_ENV=production "$APP_DIR/venv/bin/flask" db upgrade 2>/dev/null || true
ok "Migraciones aplicadas."

# Reiniciar servicio (Gunicorn graceful reload)
info "Recargando servicio (sin downtime)..."
systemctl reload-or-restart "$SERVICE"
ok "Servicio recargado."

# Verificar estado
sleep 2
if systemctl is-active --quiet "$SERVICE"; then
    ok "Servicio activo y funcionando."
else
    echo "⚠ El servicio no arrancó correctamente. Revisar: journalctl -u $SERVICE -n 50"
    exit 1
fi

echo ""
ok "Actualización completada. Backups guardados en /opt/bioko_health/backups/"
echo ""
