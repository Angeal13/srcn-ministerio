#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  BIOKO HEALTH — Servidor Central del Ministerio de Sanidad      ║
# ║                                                                  ║
# ║  Instalar UNA VEZ en el servidor del Ministerio en Malabo.      ║
# ║                                                                  ║
# ║  Recibe de: todos los nodos provinciales (internet)             ║
# ║  Cuando:    sync epidemiológico semanal + transferencias         ║
# ║                                                                  ║
# ║  Dashboard: estadísticas nacionales + alertas de brotes          ║
# ║             visibles para todo el país                           ║
# ║                                                                  ║
# ║  Uso: sudo bash instalar.sh                                      ║
# ╚══════════════════════════════════════════════════════════════════╝
set -euo pipefail

VERDE='\033[0;32m'; AMARILLO='\033[1;33m'; ROJO='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${VERDE}✓ $1${NC}"; }
info() { echo -e "${AMARILLO}→ $1${NC}"; }
err()  { echo -e "${ROJO}✗ $1${NC}"; exit 1; }

[[ $EUID -ne 0 ]] && err "Ejecutar como root."
[[ ! -f "run.py" ]] && err "Ejecutar desde el directorio raíz."

APP_DIR="/opt/bioko_health"
SERVICE_USER="bioko"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  BIOKO HEALTH — Ministerio de Sanidad · Servidor Central ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Dependencias ───────────────────────────────────────────────
info "Instalando dependencias..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    nginx mysql-server \
    libmysqlclient-dev pkg-config build-essential \
    certbot python3-certbot-nginx \
    ufw curl net-tools
ok "Dependencias instaladas."

# ── Usuario ────────────────────────────────────────────────────
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --shell /bin/bash --home-dir "$APP_DIR" --create-home "$SERVICE_USER"
fi

# ── Copiar archivos ────────────────────────────────────────────
info "Copiando archivos..."
cp -r --no-preserve=ownership . "$APP_DIR/" 2>/dev/null || true

# ── Entorno Python ─────────────────────────────────────────────
info "Instalando entorno Python..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip wheel
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
ok "Entorno Python listo."

# ── .env ───────────────────────────────────────────────────────
if [[ ! -f "$APP_DIR/.env" ]]; then
    cp "$APP_DIR/deploy/ministerio/env.template" "$APP_DIR/.env"
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s|GENERAR-python3.*|$SECRET|" "$APP_DIR/.env"
    echo ""
    echo -e "${AMARILLO}  Editar: $APP_DIR/.env${NC}"
    echo "  Cambiar: DATABASE_URL, SYNC_API_TOKEN, LAN_URL (dominio del Ministerio)"
    read -p "  ¿Listo? (s/N): " C
    [[ "$C" != "s" && "$C" != "S" ]] && err "Edite .env y vuelva a ejecutar."
fi

# ── MySQL ──────────────────────────────────────────────────────
info "Configurando MySQL..."
systemctl start mysql && systemctl enable mysql
cp "$APP_DIR/deploy/mysql_bioko.cnf" /etc/mysql/conf.d/bioko.cnf
systemctl restart mysql
DB_PASS="Bioko_$(openssl rand -hex 8)"
mysql -u root -e "
CREATE DATABASE IF NOT EXISTS bioko_health CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'bioko_user'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER,INDEX,DROP ON bioko_health.* TO 'bioko_user'@'localhost';
FLUSH PRIVILEGES;" 2>/dev/null
sed -i "s|mysql+pymysql://bioko_user:PASSWORD_MINISTERIO@localhost|mysql+pymysql://bioko_user:${DB_PASS}@localhost|" "$APP_DIR/.env"
ok "MySQL configurado."

# ── Base de datos ──────────────────────────────────────────────
info "Inicializando base de datos..."
cd "$APP_DIR"
FLASK_ENV=central "$APP_DIR/venv/bin/python" -c \
    "from app import create_app; from app.models.models import db; \
     app = create_app('central'); app.app_context().push(); db.create_all()"
FLASK_ENV=central "$APP_DIR/venv/bin/python" scripts/seed_db.py
ok "Base de datos lista."

# ── Firewall ───────────────────────────────────────────────────
info "Configurando firewall..."
ufw --force reset > /dev/null 2>&1
ufw default deny incoming
ufw default allow outgoing
read -p "  IP de administración SSH (dejar vacío para permitir cualquiera): " ADMIN_IP
if [[ -n "$ADMIN_IP" ]]; then
    ufw allow from "$ADMIN_IP" to any port 22
else
    ufw allow 22/tcp
fi
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable > /dev/null 2>&1
ok "Firewall configurado."

# ── Gunicorn ───────────────────────────────────────────────────
cp "$APP_DIR/deploy/ministerio/gunicorn.conf.py" "$APP_DIR/gunicorn.conf.py"

# ── Nginx ──────────────────────────────────────────────────────
info "Configurando Nginx..."
cp "$APP_DIR/deploy/ministerio/nginx" /etc/nginx/sites-available/bioko_health
ln -sf /etc/nginx/sites-available/bioko_health /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
ok "Nginx configurado."

# ── SSL (opcional) ─────────────────────────────────────────────
read -p "  ¿Configurar HTTPS con Let's Encrypt? Requiere dominio (s/N): " DO_SSL
if [[ "$DO_SSL" == "s" || "$DO_SSL" == "S" ]]; then
    read -p "  Dominio (ej: central.biokohealth.gq): " DOMAIN
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m admin@biokohealth.gq
    ok "HTTPS configurado para $DOMAIN"
fi

# ── Directorios ────────────────────────────────────────────────
mkdir -p /var/log/bioko_health /run/bioko_health \
         "$APP_DIR/uploads" "$APP_DIR/reports" \
         "$APP_DIR/logs" "$APP_DIR/flask_sessions"
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR" /var/log/bioko_health /run/bioko_health

# ── Systemd ────────────────────────────────────────────────────
cp "$APP_DIR/deploy/bioko_health.service" /etc/systemd/system/
systemctl daemon-reload && systemctl enable bioko_health && systemctl start bioko_health
ok "Servicio activo."

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✓ SERVIDOR CENTRAL del Ministerio instalado                 ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Acceso:     https://central.biokohealth.gq                  ║"
echo "║  Dashboard:  /pacientes/dashboard (estadísticas nacionales)  ║"
echo "║  API sync:   /api/sync/  (para nodos provinciales)           ║"
echo "║                                                              ║"
echo "║  Usuario: admin  |  Contraseña: Bioko2024!  ← CAMBIAR YA    ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  PRÓXIMO PASO: Distribuir SYNC_API_TOKEN a todos los nodos   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
