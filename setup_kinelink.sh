#!/bin/bash
set -e

echo "🚀 Installing Kinelink dependencies..."

# Update and install dependencies
sudo apt update
sudo apt install -y python3 python3-venv python3-pip apache2 curl git

# Create Kinelink directory
if [ ! -d "/opt/kinelink" ]; then
    sudo mkdir /opt/kinelink
    sudo chown $USER:$USER /opt/kinelink
fi
cd /opt/kinelink

# Clone or update repo
if [ ! -d ".git" ]; then
    git clone https://github.com/e-garbage/Kinelink .
else
    git pull
fi

# Create virtual environment
if [ ! -d ".venvkinelink" ]; then
    python3 -m venv .venvkinelink
fi

# Activate and install requirements
source .venvkinelink/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

echo "✅ Python environment ready."

# Install Apache2 reverse proxy
sudo a2enmod proxy proxy_http

# Backup default site and replace
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

# Restart Apache2
sudo systemctl restart apache2
echo "✅ Apache2 configured."

# Copy index.html
if [ -f "./html/index.html" ]; then
    sudo cp ./html/index.html /var/www/html/index.html
    echo "✅ index.html copied to /var/www/html/"
else
    echo "⚠️ No html/index.html found, skipping..."
fi

# Detect serial port
SERIAL_PORT=$(ls /dev/ttyUSB* 2>/dev/null | head -n 1 || true)
if [ -z "$SERIAL_PORT" ]; then
    echo "⚠️ No /dev/ttyUSB* device detected. You must set the serial port manually."
    SERIAL_PORT="/dev/ttyUSB0"
else
    echo "✅ Detected serial port: $SERIAL_PORT"
fi

# Create systemd service
sudo tee /etc/systemd/system/kinelink.service > /dev/null <<EOF
[Unit]
Description=Kinelink Motor Control
After=network.target

[Service]
User=$USER
WorkingDirectory=/opt/kinelink
ExecStart=/opt/kinelink/.venvkinelink/bin/python3 kinelink.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable kinelink
sudo systemctl start kinelink

# Detect host IP
HOST_IP=$(hostname -I | awk '{print $1}')

echo "🎉 Kinelink installed and running as a systemd service!"
echo "👉 Access the web interface via: http://$HOST_IP/"
