#!/usr/bin/env bash
# Nightly backup: PostgreSQL dump + uploaded media to the private S3 bucket (expired by lifecycle rule).
set -euo pipefail
. /etc/corecart/deploy.conf
stamp=$(date -u +%Y%m%dT%H%M%SZ)
runuser -u postgres -- pg_dump -Fc corecart |
  aws s3 cp - "s3://$BUCKET/backups/db/corecart-$stamp.dump" --region "$REGION" --only-show-errors
aws s3 sync /var/lib/corecart/media "s3://$BUCKET/backups/media" --region "$REGION" --only-show-errors
echo "backup $stamp OK"
