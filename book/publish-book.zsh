#!/bin/zsh

python3 -m venv venv --clear
source venv/bin/activate
pip install -r requirements.txt

./generate-dita.py
./generate-pdf.py
./generate-epub.py
