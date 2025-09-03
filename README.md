```

    ▗▖ ▗▖▗▄▄▄▖▗▖  ▗▖▗▄▄▄▖▗▖   ▗▄▄▄▖▗▖  ▗▖▗▖ ▗▖    
    ▐▌▗▞▘  █  ▐▛▚▖▐▌▐▌   ▐▌     █  ▐▛▚▖▐▌▐▌▗▞▘    
    ▐▛▚▖   █  ▐▌ ▝▜▌▐▛▀▀▘▐▌     █  ▐▌ ▝▜▌▐▛▚▖     
    ▐▌ ▐▌▗▄█▄▖▐▌  ▐▌▐▙▄▄▖▐▙▄▄▖▗▄█▄▖▐▌  ▐▌▐▌ ▐▌   
  



  developped by e-garbage for STRUCTURALS - 2025
```


# What is Kinelink
Kinelink is an step motor control program that can be interacted with through Art-Net or through a standard API. By default it is made for interacting with TMCL compatible motors, it integrate a Art-Net DMX implementation as long as a configuration web page through Apache2. It is intended to be use on RaspberryPi machines, but is Debian compatible.

# Manual Installation
Here is a step by step installation guide.
Make a directory for Kinelink on your computer

## Python backend installation
```
mkdir Kinelink && cd Kinelink
```
Clone the current repository into the Kinelink directory

```
git clone https://https://github.com/e-garbage/Kinelink
```
Create a Python virtual environnement for Kinelink to run into
```
mkdir .venvkinelink && python3 -m venv .venvkinelink
```
Activate virtual environnement
```
source .venvkinelink/bin/activate
```
install all the dependencies through pip, it can take some times :)
```
pip install -r requirements.txt
```


## Apache2 configuration server installation and setup

### Install Apache2 and activate the reverse proxy module

```
sudo apt install apache2
```
activate the reverse proxy module (it is mandatory to allow the configuration website to talk with the API, check what is a CORS context and how a reverse proxy in such context if you want to learn more)
```
sudo a2enmod proxy proxy_http
```

### Configure the reverse proxy

Now you will edit the configuration of Apache, to let it know to serve the the API on the same port and address as the website. To do so, save the current configuration file as back up:
```
sudo mv /etc/apache2/sites-available/000-default.conf /etc/apache2/sites-available/000-default.conf.bak
```
Then create a new config file with a text editor like nano
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

Finally restart Apache and wait a bit for all the change to be taken into account by the system 
```
sudo systemctl restart apache2
```

## Setup a Service for Kinelink

 *wip*

Congrats! Kinelink is now installed properly on your system




# Run and Use

To run simply use the following command inside the Kinelink directory (with the virtual environnement activated!!)

```
python3 kinelink.py
```
use `python3 kinelink.py -h` to display the help

## Available commands

```
options:
  -h, --help            show this help message and exit
  -ap ARTNET_PORT, --artnet_port ARTNET_PORT
                        ArtNet listening port, by default it commonly set on 6454
  -ai ARTNET_IP, --artnet_ip ARTNET_IP
                        ArtNet listening IP address
  -sp SERIAL_PORT, --serial_port SERIAL_PORT
                        Serial port use to communicate with the Motors
  -br BAUDRATE, --baudrate BAUDRATE
                        Baudrate use for serial communication
  -i API_IP, --api_ip API_IP
                        IP where FastAPI will send and receive messages
  -p API_PORT, --api_port API_PORT
                        Port where FastAPI will send and receive messages
  -v, --verbose         If used, switch to debugging log
  -s SPEED, --speed SPEED
                        Set the default speed for motion command like GOTOPOSITION (MVP).
  -a ACCELERATION, --acceleration ACCELERATION
                        Set the default acceleration for all motion command
```
