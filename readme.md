```

    ▗▖ ▗▖▗▄▄▄▖▗▖  ▗▖▗▄▄▄▖▗▖   ▗▄▄▄▖▗▖  ▗▖▗▖ ▗▖    
    ▐▌▗▞▘  █  ▐▛▚▖▐▌▐▌   ▐▌     █  ▐▛▚▖▐▌▐▌▗▞▘    
    ▐▛▚▖   █  ▐▌ ▝▜▌▐▛▀▀▘▐▌     █  ▐▌ ▝▜▌▐▛▚▖     
    ▐▌ ▐▌▗▄█▄▖▐▌  ▐▌▐▙▄▄▖▐▙▄▄▖▗▄█▄▖▐▌  ▐▌▐▌ ▐▌   
  



  developped by e-garbage for STRUCTURALS - 2025
```


# What is Kinelink
Kinelink is a stepper motor control program that can be interfaced via Art-Net DMX or a standard HTTP API.
It is designed for TMCL-compatible motors, and is optimized for Raspberry Pi setups, though it is compatible with Debian-based systems.
It includes:
- TMCL motor control integration
- Art-Net DMX listener
- Web-based configuration through Apache2

# Quickstart Auto installation and setup
Want to start Kinelink quickly on any Debian machine? Copy Paste this single command line into your terminal :) That's it

```
sudo bash <(curl -fsSL https://raw.githubusercontent.com/e-garbage/Kinelink/main/setup_kinelink.sh)

```


# Manual Installation Guide
Here is a step by step installation guide.
Make a directory for Kinelink on your computer

## Step 1: Prepare a Kinelink directory
```
mkdir Kinelink && cd Kinelink
```
Clone the current repository into the Kinelink directory

```
git clone https://https://github.com/e-garbage/Kinelink
```
## Step 2: Python Backend Installation
Create a Python virtual environnement for Kinelink to run into
```
mkdir .venvkinelink && python3 -m venv .venvkinelink
```
Activate it
```
source .venvkinelink/bin/activate
```
Install required dependencies:, it can take some times :)
```
pip install -r requirements.txt
```


## Step 3: Apache2 Reverse Proxy Configuration
Install Apache2:
```
sudo apt install apache2
```
activate the reverse proxy module (it is mandatory to allow the configuration website to talk with the API, check what is a CORS context and how a reverse proxy in such context if you want to learn more)
```
sudo a2enmod proxy proxy_http
```
Backup the default configuration:
```
sudo mv /etc/apache2/sites-available/000-default.conf /etc/apache2/sites-available/000-default.conf.bak
```
Edit the configuration:
```
sudo nano /etc/apache2/sites-available/000-default.conf
```
Copy the following code into the newly created file. Save and exit ( Ctrl+X then type Y and finally Enter )

```
<VirtualHost *:80>
    ServerName localhost

    DocumentRoot /var/www/html

    # Proxy /api requests to FastAPI
    ProxyPass "/api/" "http://127.0.0.1:8000/"
    ProxyPassReverse "/api/" "http://127.0.0.1:8000/"

    <Directory /var/www/html>
        Options Indexes FollowSymLinks
        AllowOverride None
        Require all granted
    </Directory>
</VirtualHost>
```

Restart Apache:
```
sudo systemctl restart apache2
```

## Step 4: Web Interface

Copy the file into the web directory:
```
sudo cp html/index.html /var/www/html
```

## Step 5: Setup Kinelink as a Service (Optional)

 *wip*

Congrats! Kinelink is now installed properly on your system




# Run and Use

To run simply use the following command inside the Kinelink directory (with the virtual environnement activated!!)

```
python3 kinelink.py
```
use `python3 kinelink.py -h` to display the help

## Available commands

| Option            | Description                                  |
| ----------------- | -------------------------------------------- |
| `-h, --help`      | Show this help message                       |
| `-ap ARTNET_PORT` | Art-Net listening port (default 6454)        |
| `-ai ARTNET_IP`   | Art-Net listening IP address                 |
| `-sp SERIAL_PORT` | Serial port for motor communication          |
| `-br BAUDRATE`    | Serial communication baudrate                |
| `-i API_IP`       | IP where FastAPI sends/receives messages     |
| `-p API_PORT`     | Port where FastAPI sends/receives messages   |
| `-v, --verbose`   | Enable debug-level logging                   |
| `-s SPEED`        | Default speed for motion commands like `MVP` |
| `-a ACCELERATION` | Default acceleration for motion commands     |



