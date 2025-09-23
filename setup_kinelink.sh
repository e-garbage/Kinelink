#!/bin/bash
set -e

# Colors
GREEN="\e[32m"
YELLOW="\e[33m"
RED="\e[31m"
RESET="\e[0m"

# Error trap
trap 'echo -e "${RED}❌ An error occurred during installation. Please check the logs above.${RESET}"' ERR

echo -e "\n🚀 ${GREEN}Starting Kinelink installation...${RESET}\n"

# Update and install dependencies
echo -e "🔧 Installing dependencies..."
sudo apt update -qq
sudo apt install -y python3 python3-venv python3-pip apache2 curl git > /dev/null
echo -e "${GREEN}✅ Dependencies installed.${RESET}\n"

# Create Kinelink directory
if [ ! -d "/opt/kinelink" ]; then
    echo "📂 Creating /opt/kinelink..."
    sudo mkdir /opt/kinelink
    sudo chown $USER:$USER /opt/kinelink
fi
cd /opt/kinelink

# Clone or update repo
if [ ! -d ".git" ]; then
    echo "📥 Cloning Kinelink repository..."
    git clone https://github.com/e-garbage/Kinelink . > /dev/null
else
    echo "🔄 Updating Kinelink repository..."
    git pull > /dev/null
fi

# Create virtual environment
if [ ! -d ".venvkinelink" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv .venvkinelink
fi

# Activate and install requirements
echo "📦 Installing Python dependencies..."
source .venvkinelink/bin/activate
pip install --upgrade pip > /dev/null
pip install -r requirements.txt > /dev/null
deactivate
echo -e "${GREEN}✅ Python environment ready.${RESET}\n"

# Apache2 setup
echo "🌐 Configuring Apache2 reverse proxy..."
sudo a2enmod proxy proxy_http > /dev/null

if [ -f "/etc/apache2/sites-available/000-default.conf" ]; then
    sudo cp /etc/apache2/sites-available/000-default.conf /etc/apache2/sites-available/000-default.conf.bak
fi

sudo tee /etc/apache2/sites-available/000-default.conf > /dev/null <<EOF
<VirtualHost *:80>
    ServerName localhost
    DocumentRoot /var/www/html

    ProxyPass "/api/" "http://127.0.0.1:8000/"
    ProxyPassReverse "/api/" "http://127.0.0.1:8000/"

    <Directory /var/www/html>
        Options Indexes FollowSymLinks
        AllowOverride None
        Require all granted
    </Directory>
</VirtualHost>
EOF

sudo systemctl restart apache2
echo -e "${GREEN}✅ Apache2 configured.${RESET}\n"

# Copy index.html
if [ -f "./html/index.html" ]; then
    sudo cp ./html/index.html /var/www/html/index.html
    echo -e "📄 index.html copied to /var/www/html/"
else
    echo -e "${YELLOW}⚠️ No html/index.html found, skipping...${RESET}"
fi

# Detect serial port
SERIAL_PORT=$(ls /dev/ttyUSB* 2>/dev/null | head -n 1 || true)
if [ -z "$SERIAL_PORT" ]; then
    echo -e "${YELLOW}⚠️ No /dev/ttyUSB* device detected. Using default /dev/ttyUSB0.${RESET}"
    SERIAL_PORT="/dev/ttyUSB0"
else
    echo -e "🔌 Detected serial port: ${GREEN}$SERIAL_PORT${RESET}"
fi

# Create systemd service
echo "🛠️ Creating systemd service..."
sudo tee /etc/systemd/system/kinelink.service > /dev/null <<EOF
[Unit]
Description=Kinelink Motor Control
After=network.target

[Service]
Type=Simple
User=$USER
WorkingDirectory=/opt/kinelink
ExecStart=/opt/kinelink/.venvkinelink/bin/python3 /opt/kinelink/kinelink.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable kinelink > /dev/null
sudo systemctl start kinelink

# Detect host IP
HOST_IP=$(hostname -I | awk '{print $1}')

echo -e "\n🎉 ${GREEN}Kinelink installed and running as a systemd service!${RESET}"
echo -e "👉 Web interface: ${YELLOW}http://$HOST_IP/${RESET}"
echo -e "👉 Service logs: ${YELLOW}sudo journalctl -u kinelink -f${RESET}\n"
