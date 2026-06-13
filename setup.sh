#!/bin/bash
# setup.sh for srcn-ministerio (Central Server)
set -e
[[ $EUID -ne 0 ]] && echo "Error: Run as root (sudo)" && exit 1

APP_DIR=$(pwd)
echo "🚀 Installing SRCN CENTRAL in $APP_DIR..."

apt update && apt install -y python3.12 python3.12-venv mysql-server nginx git openssl

# Standardize paths in config files to match current folder name
echo "--- Patching deployment configs with path: $APP_DIR ---"
# Patch service file
if [ -f "deploy/srcn.service" ]; then
    sed -i "s|/opt/srcn|$APP_DIR|g" deploy/srcn.service
    sed -i "s|/opt/bioko_health|$APP_DIR|g" deploy/srcn.service
fi
# Patch nginx file
if [ -f "deploy/nginx" ]; then
    sed -i "s|/opt/srcn|$APP_DIR|g" deploy/nginx
    sed -i "s|/opt/bioko_health|$APP_DIR|g" deploy/nginx
fi

# User & Folders
id bioko &>/dev/null || useradd -r -s /usr/sbin/nologin -d "$APP_DIR" bioko
mkdir -p "$APP_DIR/logs" "$APP_DIR/instance" "$APP_DIR/backups" "$APP_DIR/uploads" "$APP_DIR/reports"
chown -R bioko:bioko "$APP_DIR"

# Database
DB_PASS=$(openssl rand -hex 12)
mysql -e "CREATE DATABASE IF NOT EXISTS srcn_central; CREATE USER IF NOT EXISTS 'bioko_user'@'localhost' IDENTIFIED BY '$DB_PASS'; GRANT ALL PRIVILEGES ON srcn_central.* TO 'bioko_user'@'localhost'; FLUSH PRIVILEGES;"

# App Setup
python3.12 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Config & Token Generation
cp .env.template .env
SEC_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
SYNC_TOK=$(python3 -c "import secrets; print(secrets.token_hex(32))")
sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SEC_KEY|" .env
sed -i "s|SYNC_API_TOKEN=.*|SYNC_API_TOKEN=$SYNC_TOK|" .env
sed -i "s|bioko_user:.*@localhost|bioko_user:$DB_PASS@localhost|g" .env
# Update DB name if needed in .env
sed -i "s|localhost/bioko_health|localhost/srcn_central|g" .env

# Initialize DB (SQL Generation)
# Assuming it uses a similar script or just db.create_all via a python command
if [ -f "scripts/seed_db.py" ]; then
    ./venv/bin/python scripts/seed_db.py
else
    ./venv/bin/python -c "from app import create_app; from app.models.models import db; app = create_app('production'); app.app_context().push(); db.create_all()"
fi

# SSL & Nginx
mkdir -p /etc/ssl/srcn
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/ssl/srcn/privkey.pem -out /etc/ssl/srcn/fullchain.pem -subj "/C=GQ/L=Malabo/O=Ministry/CN=srcn.gq"
# Update nginx to use these certificates
if [ -f "deploy/nginx" ]; then
    sed -i "s|/etc/letsencrypt/live/central.biokohealth.gq/fullchain.pem|/etc/ssl/srcn/fullchain.pem|g" deploy/nginx
    sed -i "s|/etc/letsencrypt/live/central.biokohealth.gq/privkey.pem|/etc/ssl/srcn/privkey.pem|g" deploy/nginx
    # Ensure SSL lines are active (uncomment if they were commented)
    sed -i 's/# ssl_certificate/ssl_certificate/g' deploy/nginx
    cp deploy/nginx /etc/nginx/sites-available/srcn
    ln -sf /etc/nginx/sites-available/srcn /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
fi

# System Service (Run on Boot)
if [ -f "deploy/srcn.service" ]; then
    cp deploy/srcn.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable mysql nginx srcn
    systemctl restart mysql nginx srcn
fi

echo "✅ SRCN CENTRAL SETUP COMPLETE"
echo "MASTER SYNC TOKEN (Give this to all other nodes): $SYNC_TOK"
