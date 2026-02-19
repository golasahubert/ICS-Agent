#!/bin/bash

echo "==========================================="
echo "   ICS HOneypot agent"
echo "==========================================="

if [ ! -d "venv" ]; then
    echo "[*] Creating virtual evn (venv)..."
    python3 -m venv venv
else
    echo "[*] Already found(venv)."
fi


echo "[*] Activating.."
source venv/bin/activate

echo "[*] IInstalling dependencies  requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[*] Browsers Playwright..."
playwright install chromium firefox
playwright install-deps

echo "-------------------------------------------"
echo "   Starting testing Honeypots"
echo "-------------------------------------------"

echo "[->]  1-CustomHMI.py"
python 1-CustomHMI.py
echo ""

echo "[->]  2.ScadaBR.py"
python 2.ScadaBR.py
echo ""

echo "[->] 3.ScadaBR-no-B.py"
python 3.ScadaBR-no-B.py
echo ""

echo "[->]  4.ScadaLTS.py"
python 4.ScadaLTS.py
echo ""

echo "==========================================="
echo "   Test finished."
echo "==========================================="

deactivate