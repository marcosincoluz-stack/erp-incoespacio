#!/bin/bash
# Hooks para el certbot.timer de Ubuntu: Nginx usa copias en nginx/ssl/
# y el alta fue --standalone (puerto 80). Sin esto, la renovación choca con Nginx
# y el contenedor sigue el certificado viejo.
set -euo pipefail

PROD="${PROD:-/opt/erp/prod}"
LIVE="${LIVE:-/etc/letsencrypt/live/erp.incoespacio.com}"
DEST="${PROD}/nginx/ssl"

install -d /etc/letsencrypt/renewal-hooks/pre /etc/letsencrypt/renewal-hooks/post

cat > /etc/letsencrypt/renewal-hooks/pre/00-stop-nginx << EOF
#!/bin/bash
set -e
export PATH=/usr/local/bin:/usr/bin:/bin
cd ${PROD}
docker compose stop nginx
EOF

cat > /etc/letsencrypt/renewal-hooks/post/00-copy-certs-start-nginx << EOF
#!/bin/bash
set -e
export PATH=/usr/local/bin:/usr/bin:/bin
cp ${LIVE}/fullchain.pem ${DEST}/fullchain.pem
cp ${LIVE}/privkey.pem ${DEST}/privkey.pem
chown ubuntu:ubuntu ${DEST}/fullchain.pem ${DEST}/privkey.pem
chmod 644 ${DEST}/fullchain.pem
chmod 600 ${DEST}/privkey.pem
cd ${PROD}
docker compose start nginx || docker compose up -d nginx
EOF

chmod 755 /etc/letsencrypt/renewal-hooks/pre/00-stop-nginx
chmod 755 /etc/letsencrypt/renewal-hooks/post/00-copy-certs-start-nginx
echo "Hooks instalados. Probar: sudo certbot renew --dry-run"
