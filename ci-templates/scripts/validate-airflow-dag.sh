#!/usr/bin/env bash
set -euo pipefail

DAG_DIR="${DAG_DIR:-.}"

if [ ! -d "${DAG_DIR}" ]; then
  echo "dag dir ${DAG_DIR} not found" >&2
  exit 1
fi

status=0
while IFS= read -r -d '' f; do
  echo "checking $f"
  if ! python3 -m py_compile "$f"; then
    echo "syntax error in $f" >&2
    status=1
  fi
  if ! grep -q "dag_id" "$f"; then
    echo "warning: $f has no dag_id reference" >&2
  fi
done < <(find "${DAG_DIR}" -name '*.py' -print0)

exit $status
