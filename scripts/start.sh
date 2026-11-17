#!/bin/bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ -L venv-current ]]; then
  exec venv-current/bin/python app.py --host=0.0.0.0 --port=81
fi
if [[ ! -x venv/bin/python ]]; then
  echo 'No environment installed. Follow the deployment instructions first.' >&2
  exit 1
fi
exec venv/bin/python app.py --host=0.0.0.0 --port=81
