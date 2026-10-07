#!/usr/bin/env bash
# Runs inside the disposable bench container started by run.sh.
set -Eeuo pipefail

cd /home/frappe/frappe-bench
node_bin="$(find /home/frappe/.nvm/versions/node -maxdepth 2 -name bin -type d | head -n 1)"
export PATH="${PWD}/env/bin:${node_bin}:${PATH}"

echo "== Versions"
bench version

echo "== Configure bench"
bench set-config -g db_host db
bench set-config -gp db_port 3306
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379

echo "== Install the app into the bench"
# The checkout is mounted from the host, so another user owns it.
git config --global --add safe.directory /home/frappe/access_grants
bench get-app --soft-link /home/frappe/access_grants

echo "== Create site"
# The app only needs Frappe; the tests use ERPNext's Employee and Timesheet.
bench new-site \
    --mariadb-user-host-login-scope='%' \
    --admin-password admin \
    --db-root-password "${DB_ROOT_PASSWORD}" \
    --install-app erpnext \
    --install-app access_grants \
    "${SITE_NAME}"
bench --site "${SITE_NAME}" set-config allow_tests true

echo "== Tests"
bench --site "${SITE_NAME}" run-tests --app access_grants

echo "== All tests passed"
