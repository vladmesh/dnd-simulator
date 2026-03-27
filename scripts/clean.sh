#!/usr/bin/env bash
# Kill dev processes and wipe accumulated artifacts.
set -euo pipefail

SELF_PID=$$

kill_port() {
    local port=$1
    local pids
    pids=$(lsof -ti "tcp:$port" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        echo "$pids" | xargs kill 2>/dev/null || true
        echo "  Killed port $port ($pids)"
    else
        echo "  Port $port free"
    fi
}

kill_pattern() {
    local pattern=$1
    local label=$2
    local pids
    pids=$(pgrep -f "$pattern" 2>/dev/null | grep -v "^${SELF_PID}$" || true)
    if [[ -n "$pids" ]]; then
        echo "$pids" | xargs kill 2>/dev/null || true
        echo "  Killed $label ($pids)"
    else
        echo "  No $label processes"
    fi
}

echo "=== Killing processes ==="
kill_port 8001
kill_port 5173
kill_pattern 'playwright' 'playwright'
kill_pattern 'chromium.*--remote-debugging' 'chromium'

echo "=== Cleaning artifacts ==="
count=$(find saves/ -mindepth 1 ! -name '.gitkeep' -delete -print 2>/dev/null | wc -l || echo 0)
echo "  saves/: $count files removed"

count=$(find logs/ -mindepth 1 -delete -print 2>/dev/null | wc -l || echo 0)
echo "  logs/: $count files removed"

count=0
for ext in png jpeg log; do
    n=$(find .playwright-mcp/ -maxdepth 1 -name "*.$ext" -delete -print 2>/dev/null | wc -l || echo 0)
    count=$((count + n))
done
echo "  .playwright-mcp/: $count files removed"

echo "=== Done ==="
