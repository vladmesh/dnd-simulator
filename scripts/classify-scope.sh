#!/bin/bash
# Classify a set of changed file paths into a test scope.
#
# Reads file paths one per line from stdin, prints exactly one of:
#   docs      — only docs/** or *.md changed, nothing to test
#   frontend  — only frontend/** (plus docs) changed
#   backend   — only known backend paths (plus docs) changed
#   mixed     — both scopes touched, or any unrecognized/infra path
#               (Makefile, scripts/, .github/, orca.yaml, docker*, ...)
#
# Safe default: any ambiguity classifies as "mixed" so callers run the
# full suite instead of skipping something that mattered.
set -euo pipefail

has_frontend=0
has_docs=0
has_backend=0
has_mixed=0
has_any=0

while IFS= read -r path; do
    [ -z "$path" ] && continue
    has_any=1
    case "$path" in
        *.md)
            has_docs=1
            ;;
        docs/*)
            has_docs=1
            ;;
        frontend/*)
            has_frontend=1
            ;;
        src/*|tests/*|content/*|pyproject.toml|uv.lock|.python-version)
            has_backend=1
            ;;
        *)
            has_mixed=1
            ;;
    esac
done

if [ "$has_any" -eq 0 ]; then
    echo "mixed"
    exit 0
fi

if [ "$has_mixed" -eq 1 ]; then
    echo "mixed"
elif [ "$has_frontend" -eq 1 ] && [ "$has_backend" -eq 1 ]; then
    echo "mixed"
elif [ "$has_frontend" -eq 1 ]; then
    echo "frontend"
elif [ "$has_backend" -eq 1 ]; then
    echo "backend"
elif [ "$has_docs" -eq 1 ]; then
    echo "docs"
else
    echo "mixed"
fi
