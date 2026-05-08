#!/bin/bash
# Context Market Backup Script
# Run daily via cron: 0 3 * * * /root/.openclaw/workspace/innovations/context-market-v2/infra/backup.sh

set -e

BACKUP_DIR="/var/backups/context-market"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

echo "=== Context Market Backup — $DATE ==="

# Create backup directory
mkdir -p "$BACKUP_DIR"

# 1. Database backup
echo "Backing up PostgreSQL database..."
pg_dump -h localhost -U context -d contextmarket \
    | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# 2. Application code backup
echo "Backing up application code..."
tar czf "$BACKUP_DIR/code_$DATE.tar.gz" \
    -C /root/.openclaw/workspace/innovations/context-market-v2 \
    backend/ frontend/ infra/ skill.md README.md

# 3. Environment/config backup
echo "Backing up config..."
tar czf "$BACKUP_DIR/config_$DATE.tar.gz" \
    -C /root/.openclaw/workspace/innovations/context-market-v2/backend \
    .env

# 4. Clean old backups
echo "Cleaning backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -type f -mtime +$RETENTION_DAYS -delete

# 5. Summary
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo ""
echo "=== Backup Complete ==="
echo "Location: $BACKUP_DIR"
echo "Size: $BACKUP_SIZE"
echo "Files:"
ls -lh "$BACKUP_DIR"/*_$DATE* 2>/dev/null || echo "  (files listed above)"
echo ""
