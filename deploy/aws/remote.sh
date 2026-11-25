#!/usr/bin/env bash
# Runs ON the EC2 instance (Amazon Linux 2023, arm64) via SSM Run Command, as root.
# Idempotent: first run bootstraps the box, every run installs a release.
#
#   remote.sh release <release-dir>   # install the extracted release, migrate, switch, health check
#   remote.sh config                  # re-read config from SSM and restart (no new code)
#   remote.sh manage <args...>        # run a manage.py command as the app user
set -euo pipefail

APP=/opt/corecart
DATA=/var/lib/corecart
ETC=/etc/corecart
REGION=${AWS_REGION:-us-east-1}
PARAM_PREFIX=${CORECART_PARAM_PREFIX:-/corecart}
export UV_PYTHON_INSTALL_DIR=$APP/python UV_CACHE_DIR=/var/cache/corecart-uv UV_NO_PROGRESS=1
export PATH=/usr/local/bin:$PATH

log() { echo "[corecart] $*"; }

param() {
  aws ssm get-parameter --region "$REGION" --with-decryption --name "$PARAM_PREFIX/$1" \
    --query Parameter.Value --output text
}

bootstrap() {
  log "bootstrap: packages"
  # Swap: the t4g.micro has 1 GB RAM.
  if ! swapon --show | grep -q /swapfile; then
    fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
    grep -q /swapfile /etc/fstab || echo '/swapfile none swap defaults 0 0' >> /etc/fstab
  fi
  local pg=""
  for v in 17 16 15; do
    if dnf list --available "postgresql$v-server" >/dev/null 2>&1 || rpm -q "postgresql$v-server" >/dev/null 2>&1; then pg=$v; break; fi
  done
  [ -n "$pg" ] || { echo "no postgresql server package found" >&2; exit 1; }
  local redis_pkg=redis6 redis_svc=redis6 redis_conf=/etc/redis6/redis6.conf
  if ! dnf list --available redis6 >/dev/null 2>&1 && ! rpm -q redis6 >/dev/null 2>&1; then
    redis_pkg=valkey redis_svc=valkey redis_conf=/etc/valkey/valkey.conf
  fi
  dnf install -y -q nginx "postgresql$pg-server" "postgresql$pg" "$redis_pkg" tar gzip >/dev/null
  dnf upgrade -y -q --security >/dev/null || true

  # Automatic security updates (applied nightly, no reboot).
  cat > /etc/systemd/system/corecart-security-updates.service <<'EOF'
[Unit]
Description=Apply security updates
[Service]
Type=oneshot
ExecStart=/usr/bin/dnf upgrade -y -q --security
EOF
  cat > /etc/systemd/system/corecart-security-updates.timer <<'EOF'
[Unit]
Description=Nightly security updates
[Timer]
OnCalendar=*-*-* 04:30:00
RandomizedDelaySec=30m
Persistent=true
[Install]
WantedBy=timers.target
EOF

  log "bootstrap: users and directories"
  id corecart >/dev/null 2>&1 || useradd --system --home-dir "$APP" --shell /sbin/nologin corecart
  install -d -m 755 "$APP" "$APP/releases"
  install -d -m 750 -o corecart -g corecart "$DATA" "$DATA/media" "$DATA/static"
  chmod 755 "$DATA" "$DATA/static" "$DATA/media"   # nginx serves static/media
  install -d -m 750 -o root -g corecart "$ETC"

  log "bootstrap: postgresql $pg"
  if [ ! -f /var/lib/pgsql/data/PG_VERSION ]; then
    postgresql-setup --initdb >/dev/null
  fi
  # Small-box tuning; local connections only (peer auth over the unix socket, no password).
  cat > /var/lib/pgsql/data/conf.d-corecart.conf <<'EOF'
listen_addresses = ''
max_connections = 30
shared_buffers = 64MB
work_mem = 4MB
maintenance_work_mem = 32MB
effective_cache_size = 256MB
EOF
  chown postgres:postgres /var/lib/pgsql/data/conf.d-corecart.conf
  grep -q "conf.d-corecart.conf" /var/lib/pgsql/data/postgresql.conf ||
    echo "include_if_exists = 'conf.d-corecart.conf'" >> /var/lib/pgsql/data/postgresql.conf
  systemctl enable --now postgresql >/dev/null
  systemctl restart postgresql
  runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='corecart'" | grep -q 1 ||
    runuser -u postgres -- createuser corecart
  runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='corecart'" | grep -q 1 ||
    runuser -u postgres -- createdb -O corecart corecart

  log "bootstrap: $redis_svc"
  # Loopback only (package default), small memory cap, no persistence needed (cache + rate limits).
  sed -i -E 's/^#? ?maxmemory .*/maxmemory 64mb/; s/^#? ?maxmemory-policy .*/maxmemory-policy allkeys-lru/' "$redis_conf"
  grep -q '^maxmemory ' "$redis_conf" || echo 'maxmemory 64mb' >> "$redis_conf"
  grep -q '^maxmemory-policy ' "$redis_conf" || echo 'maxmemory-policy allkeys-lru' >> "$redis_conf"
  sed -i -E 's/^save .*//' "$redis_conf"
  grep -q '^save ""' "$redis_conf" || echo 'save ""' >> "$redis_conf"
  systemctl enable --now "$redis_svc" >/dev/null
  systemctl restart "$redis_svc"
  echo "$redis_svc" > "$ETC/redis-service"

  log "bootstrap: uv"
  if ! command -v uv >/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh >/dev/null
  fi
  install -d -m 755 "$APP/python" "$UV_CACHE_DIR"

  systemctl daemon-reload
  systemctl enable --now corecart-security-updates.timer >/dev/null
  touch "$ETC/.bootstrapped-v1"
}

write_config() {
  log "config: environment from SSM Parameter Store"
  umask 027
  param env > "$ETC/env.new"
  chown root:corecart "$ETC/env.new" && chmod 640 "$ETC/env.new" && mv "$ETC/env.new" "$ETC/env"
  local secret bucket
  secret=$(param origin-secret)
  bucket=$(param bucket)
  umask 022
  printf 'BUCKET=%s\nREGION=%s\n' "$bucket" "$REGION" > "$ETC/deploy.conf"
  # Only CloudFront knows this header value; anything else that reaches port 80 gets 403.
  printf 'map $http_x_origin_verify $corecart_origin_ok {\n    default 0;\n    "%s" 1;\n}\n' "$secret" \
    > /etc/nginx/conf.d/00-corecart-origin.conf.new
  chmod 640 /etc/nginx/conf.d/00-corecart-origin.conf.new
  chgrp nginx /etc/nginx/conf.d/00-corecart-origin.conf.new
  mv /etc/nginx/conf.d/00-corecart-origin.conf.new /etc/nginx/conf.d/00-corecart-origin.conf
}

install_units() {
  local rel=$1 admin redis_svc
  admin=$(grep '^DJANGO_ADMIN_URL=' "$ETC/env" | cut -d= -f2- | sed 's#^/*##; s#/*$##')
  redis_svc=$(cat "$ETC/redis-service")
  cp "$rel/deploy/aws/proxy_params" /etc/nginx/corecart_proxy_params
  sed "s#__ADMIN_URL__#$admin#g" "$rel/deploy/aws/nginx.conf" > /etc/nginx/conf.d/corecart.conf
  # Drop the stock default server so ours is the only one on :80.
  sed -i '/^    server {/,/^    }/d' /etc/nginx/nginx.conf
  nginx -t -q
  sed "s#__REDIS__#$redis_svc#g" "$rel/deploy/aws/corecart.service" > /etc/systemd/system/corecart.service
  cp "$rel/deploy/aws/corecart-backup.service" "$rel/deploy/aws/corecart-backup.timer" /etc/systemd/system/
  install -m 755 "$rel/deploy/aws/backup.sh" /usr/local/bin/corecart-backup
  install -m 755 "$rel/deploy/aws/manage.sh" /usr/local/bin/corecart-manage
  systemctl daemon-reload
  systemctl enable --now nginx corecart-backup.timer >/dev/null
  systemctl enable corecart >/dev/null
}

health_check() {
  local host secret
  host=$(grep '^DJANGO_ALLOWED_HOSTS=' "$ETC/env" | cut -d= -f2 | cut -d, -f1)
  secret=$(param origin-secret)
  for _ in $(seq 1 20); do
    if curl -fsS -o /dev/null -H "Host: $host" -H "X-Origin-Verify: $secret" http://127.0.0.1/api/v1/health/; then
      return 0
    fi
    sleep 2
  done
  return 1
}

release() {
  local rel=$1 prev=""
  [ -f "$ETC/.bootstrapped-v1" ] || bootstrap
  write_config
  log "release: python dependencies ($rel)"
  cd "$rel"
  UV_PROJECT_ENVIRONMENT="$rel/.venv" uv sync --frozen --no-dev --extra production --compile-bytecode -q
  chmod -R a+rX "$rel" "$APP/python"

  log "release: migrate + collectstatic + checks"
  install -m 755 "$rel/deploy/aws/manage.sh" /usr/local/bin/corecart-manage
  CORECART_DIR=$rel /usr/local/bin/corecart-manage migrate --noinput
  CORECART_DIR=$rel /usr/local/bin/corecart-manage collectstatic --noinput -v 0
  CORECART_DIR=$rel /usr/local/bin/corecart-manage check --deploy --fail-level ERROR

  [ -L "$APP/current" ] && prev=$(readlink -f "$APP/current")
  ln -sfn "$rel" "$APP/current.new" && mv -T "$APP/current.new" "$APP/current"
  install_units "$rel"
  systemctl restart corecart
  systemctl reload nginx

  if ! health_check; then
    echo "health check FAILED" >&2
    journalctl -u corecart -n 40 --no-pager >&2 || true
    if [ -n "$prev" ] && [ "$prev" != "$rel" ]; then
      echo "rolling back to $prev" >&2
      ln -sfn "$prev" "$APP/current.new" && mv -T "$APP/current.new" "$APP/current"
      systemctl restart corecart
    fi
    exit 1
  fi
  # Keep the last 3 releases.
  ls -1dt "$APP"/releases/*/ | tail -n +4 | xargs -r rm -rf
  log "release OK: $(basename "$rel")"
}

case "${1:-}" in
  release) release "$2" ;;
  config)
    write_config
    install_units "$(readlink -f "$APP/current")"
    systemctl restart corecart && systemctl reload nginx
    health_check && log "config applied" ;;
  manage) shift; /usr/local/bin/corecart-manage "$@" ;;
  *) echo "usage: $0 release <dir> | config | manage <args>" >&2; exit 2 ;;
esac
