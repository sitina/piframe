#!/bin/bash
set -e

if [ ! -d "venv/" ]; then
  echo "Initialising virtualenv - this is one off"
  python3 -m venv venv
  echo "virtualenv initialisation done"
fi

source venv/bin/activate
pip3 install -U -r requirements.txt
flask run --host=0.0.0.0
deactivate
