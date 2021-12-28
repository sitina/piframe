#!/bin/bash
set -e

if [ ! -d "venv/" ]; then
  echo "Initialising virtualenv - this is one off"
  virtualenv -p python3 venv
  echo "virtualenv initialisation done"
fi

source venv/bin/activate
flask run --host=0.0.0.0
deactivate
