#!/usr/bin/env bash
set -euo pipefail

cd /app
export PORT="${PORT:-10000}"
api_pid=""
web_pid=""
phase_pid=""

cleanup() {
    local status=$?
    trap - EXIT TERM INT
    local pids=()
    for pid in "$api_pid" "$web_pid" "$phase_pid"; do
        if [[ -n "$pid" ]]; then
            pids+=("$pid")
            kill -TERM -- "-$pid" 2>/dev/null || true
        fi
    done
    # Bound graceful shutdown, including Gunicorn's workers and startup tasks.
    (
        sleep 25
        for pid in "${pids[@]}"; do kill -KILL -- "-$pid" 2>/dev/null || true; done
    ) &
    local watchdog=$!
    for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || true; done
    kill "$watchdog" 2>/dev/null || true
    wait "$watchdog" 2>/dev/null || true
    exit "$status"
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

run_phase() {
    setsid "$@" &
    phase_pid=$!
    local finished="" status=0
    if [[ -n "$api_pid" ]]; then
        wait -n -p finished "$api_pid" "$phase_pid" || status=$?
        if [[ "$finished" == "$api_pid" ]]; then
            echo "FastAPI exited during startup (status $status)." >&2
            exit 1
        fi
    else
        wait "$phase_pid" || status=$?
    fi
    phase_pid=""
    if (( status != 0 )); then exit "$status"; fi
}

# Validate Django configuration before either application can migrate a database.
cd /app/web
run_phase python manage.py check
cd /app/api
run_phase alembic upgrade head
setsid uvicorn app.main:app --host 127.0.0.1 --port 8001 &
api_pid=$!

# Do not advertise a healthy Django until the internal API accepts requests.
run_phase python -c '
import time, urllib.request
for attempt in range(60):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8001/health", timeout=1) as response:
            assert response.status == 200
        break
    except (OSError, AssertionError):
        time.sleep(0.5)
else:
    raise SystemExit("FastAPI did not become ready")
'
cd /app/web
run_phase python manage.py migrate --noinput
run_phase python manage.py collectstatic --noinput
setsid gunicorn config.wsgi:application --bind "0.0.0.0:$PORT" --workers 2 --access-logfile - &
web_pid=$!

status=0
wait -n "$api_pid" "$web_pid" || status=$?
echo "A critical server exited (status $status); stopping both servers." >&2
# Even a clean, unexpected server exit must cause a container restart.
exit 1
