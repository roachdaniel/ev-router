#!/usr/bin/env bash
# First-time deploy to PinkiPi. Subsequent deploys use deploy-pinkipi.sh.
set -euo pipefail

REMOTE="pi@192.168.1.8"

echo "→ Deploying EV Router to $REMOTE"

ssh "$REMOTE" bash <<'ENDSSH'
set -e

# Clone or pull
if [ ! -d ~/ev-router/.git ]; then
  git clone https://github.com/roachdaniel/ev-router.git ~/ev-router
else
  git -C ~/ev-router pull --ff-only
fi

# Virtualenv
if [ ! -f ~/ev-router/venv/bin/activate ]; then
  python3 -m venv ~/ev-router/venv
fi
source ~/ev-router/venv/bin/activate
pip install -q -r ~/ev-router/requirements.txt

# .env skeleton if not present
if [ ! -f ~/ev-router/.env ]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  cat > ~/ev-router/.env <<EOF
SECRET_KEY=$SECRET
GOOGLE_MAPS_SERVER_KEY=
GOOGLE_MAPS_JS_KEY=
EOF
  echo "⚠  Created ~/ev-router/.env — fill in API keys before using"
fi

# Install and start service
sudo cp ~/ev-router/ev-router.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ev-router
sudo systemctl restart ev-router

echo "✓ EV Router running on port 5002"
ENDSSH
