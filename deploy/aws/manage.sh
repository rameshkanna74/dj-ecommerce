#!/usr/bin/env bash
# corecart-manage: run manage.py as the unprivileged app user with the production environment.
#   sudo corecart-manage createsuperuser
#   sudo corecart-manage shell
set -euo pipefail
DIR=${CORECART_DIR:-/opt/corecart/current}
set -a
# shellcheck disable=SC1091
. /etc/corecart/env
set +a
cd "$DIR"
exec runuser -u corecart -- "$DIR/.venv/bin/python" manage.py "$@"
