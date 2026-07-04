#!/bin/bash
# Install git hooks from .githooks/ into .git/hooks/

set -e

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$REPO_ROOT"

chmod +x .githooks/pre-commit .githooks/pre-push scripts/classify-scope.sh

GIT_HOOKS_DIR=$(git rev-parse --git-path hooks)
mkdir -p "$GIT_HOOKS_DIR"

for hook in pre-commit pre-push; do
    if ! ln -sf "$REPO_ROOT/.githooks/$hook" "$GIT_HOOKS_DIR/$hook"; then
        cp -f "$REPO_ROOT/.githooks/$hook" "$GIT_HOOKS_DIR/$hook"
    fi
done

git config core.hooksPath .git/hooks

echo "Git hooks installed."
