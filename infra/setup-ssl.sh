#!/bin/bash
# SSL Setup Script for Context Market
# Run this after pointing domain A-record to server IP

set -e

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <domain.com>"
    exit 1
fi

echo "=== Setting up SSL for $DOMAIN ==="

# 1. Install certbot
echo "Installing certbot..."
apt-get update -qq
apt-get install -y -qq certbot python3-certbot-nginx

# 2. Create nginx config from template
echo "Creating nginx config..."
sed "s/DOMAIN_NAME/$DOMAIN/g" /root/.openclaw/workspace/innovations/context-market-v2/infra/nginx-ssl.conf \
    > /etc/nginx/sites-available/context-market

# 3. Enable site
ln -sf /etc/nginx/sites-available/context-market /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 4. Test nginx config
nginx -t

# 5. Reload nginx
systemctl reload nginx

# 6. Get SSL certificate
echo "Requesting SSL certificate from Let's Encrypt..."
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@$DOMAIN

# 7. Auto-renewal (certbot handles this, but verify)
echo "Verifying auto-renewal..."
certbot renew --dry-run

echo ""
echo "=== SSL Setup Complete ==="
echo "Domain: https://$DOMAIN"
echo "API: https://$DOMAIN"
echo "Docs: https://$DOMAIN/docs"
echo ""
echo "Test with:"
echo "  curl -s https://$DOMAIN/docs | head -1"
