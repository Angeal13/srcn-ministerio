#!/bin/bash
# SRCN — Script de instalación para nodo comisaría
set -e

echo "=== SRCN — Instalación Nodo Comisaría ==="
echo "Ministerio del Interior · Guinea Ecuatorial"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then echo "Ejecutar como root"; exit 1; fi

# Install system packages
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv nginx sqlite3 git curl

# Create service user
useradd -r -s /bin/false srcn 2>/dev/null || true
mkdir -p /opt/srcn
cd /opt/srcn

# Python venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r /tmp/srcn_install/requirements.txt -q

# Env file
if [ ! -f /opt/srcn/.env ]; then
  cp deploy/.env.template /opt/srcn/.env
  echo "IMPORTANTE: Editar /opt/srcn/.env con los valores de esta comisaría"
fi

# Create DB
flask --app run db upgrade 2>/dev/null || python3 -c "from app import create_app; from app.models.models import db; app=create_app('production'); app.app_context().push(); db.create_all()"
python3 scripts/seed_db.py

# Systemd service
cp deploy/srcn.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable srcn
systemctl start srcn

# Nginx
cp deploy/nginx /etc/nginx/sites-available/srcn
ln -sf /etc/nginx/sites-available/srcn /etc/nginx/sites-enabled/srcn
nginx -t && systemctl reload nginx

echo ""
echo "=== Instalación completada ==="
echo "Acceder en: http://$(hostname -I | awk '{print $1}'):80"
echo "Credenciales iniciales: admin / srcn_admin_2026"
echo "CAMBIAR CONTRASEÑA INMEDIATAMENTE"
