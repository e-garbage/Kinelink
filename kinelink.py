import socket
import struct
import asyncio
import logging
from TMCL import MotorManager
import web_api
import uvicorn
from rich.logging import RichHandler
from rich.console import Console
import os
import argparse
import math
import time

#CHANGE VERSION NUMBER HERE
version=1.0
console=Console()




"""
Start FastAPI app
- start artnet listener
- scan for RS485/serial connected motors
- scan for connected motors
- lauch motor control manager
  ├── Receives high-level motion commands from ArtNet or API
  ├── Queues or batches motor instructions
  └── Serial worker sends commands over RS485 one at a time
-  API (FastAPI)
   ├── /calibrate
   ├── /status
   └── /move

TMCL commands sent every Artnet Tick if Artnet activated/available, otherwise fake tick with async loop


kinelink.py
scanner.py
utils.py
requirements.txt
/web

web part:
- served with apache/nginx
- connect to the fastAPI
- responsive UI (developped for mobile)
- lightweight, no heavy JS framework

-> calibrate motors
-> set min/max
-> move motors
-> set speed
-> set ArtNet mode
-> panic mode (stop all motors)
-> set ArtNet universe + listening port

API commands:
##tmcl motion commands
/moveleft (addr, speed)
/moveright (addr, speed)
/stop (addr)
/setref (addr)
/gotopos (addr, pos, speed)

##tmcl parameters commands
/setmin (addr, pos)
/setmax (addr, pos)
/setspeed (addr, speed)
/setaccel (addr, accel)
/gettemp (addr)
/getpos (addr)
/panic (addr)
/scan ()

## ArtNet commands
/setartnetuniverse (value)
/setartnetport (ip)
/artnet_on (bool)


DMX commands per motor address:
CH1: moveleft (speed 2 - 255; stop 0 - 1)
CH2: moveright (speed 2 - 255; stop 0 - 1)
CH3: gotohome (0-5); 


"""

class utils: 
    def clear():
        """clear system console"""
        os.system('cls' if os.name=='nt' else 'clear')
    
    def art():
        console.print("""

▗▖ ▗▖▗▄▄▄▖▗▖  ▗▖▗▄▄▄▖▗▖   ▗▄▄▄▖▗▖  ▗▖▗▖ ▗▖    
▐▌▗▞▘  █  ▐▛▚▖▐▌▐▌   ▐▌     █  ▐▛▚▖▐▌▐▌▗▞▘    
▐▛▚▖   █  ▐▌ ▝▜▌▐▛▀▀▘▐▌     █  ▐▌ ▝▜▌▐▛▚▖     
▐▌ ▐▌▗▄█▄▖▐▌  ▐▌▐▙▄▄▖▐▙▄▄▖▗▄█▄▖▐▌  ▐▌▐▌ ▐▌   
                                            
""", style="red", justify="center")
        console.print("by STRUCTURALS", style="bold red reverse", justify="center")
        console.print(f"\ndevelopped by e-garbage 2025, v{version}\n\n", style="italic red", justify="center", highlight=False)

    def verbose_mode(verbose:bool):
        if verbose == True:
            log_mod=logging.DEBUG
        else:
            log_mod=logging.INFO

        LOGGING_FORMAT='%(message)s'
        logging.basicConfig(level=log_mod, format=LOGGING_FORMAT, handlers=[RichHandler(rich_tracebacks=False, show_path=True, markup=True)])


dmx_data = [0] * 512  # Global DMX buffer for 512

## Artnet listener background task
async def artnet_listener(port=6454, ip="192.168.1.100", pause=False, universe=20):
    """
    Asynchronous listener for ArtNet packets on a specified port and IP address.
    Args: 
        port (int): Port to listen on. Default is 6454.
        ip (str): IP address to bind to. Default is 192.168.1.100
        pause (bool): If True, pauses the listener. Default is False.
        universe (int): ArtNet universe to listen to. Default is 20.
    """
    loop = asyncio.get_event_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(False)
    logging.debug("artnet_simulated")
    try:
        sock.bind((ip, port))
        logging.debug(f"Listening on {ip}:{port}")
    except Exception as e:
        logging.error({e})
        return
        
    while True:
        
        if pause== True:
            logging.debug("ArtNet listener paused")
            asyncio.sleep(0.1)
            continue
        try:
            data, addr = await loop.sock_recvfrom(sock, 1024)
            opcode   = struct.unpack('<H', data[8:10])[0]
            u = struct.unpack('<H', data[14:16])[0]
            # check artnet packet structure and drop non-ArtNet packets
            if len(data) < 18 or not data.startswith(b'Art-Net\x00'):
                continue
            if opcode != 0x5000 or u != universe:
                continue
            raw_dmx = data[18:]
            await motor_control_manager.apply_artnet_frame(raw_dmx) # <---------------------------------------------------------------------------------------
            # Met à jour in-place le buffer global DMX (512 canaux)
            for i in range(512):
                dmx_data[i] = raw_dmx[i] if i < len(raw_dmx) else 0
            logging.debug(f"[DMX RX] ch1–16: {dmx_data[:16]}")

        except Exception as e:
            logging.error(f"[ARTNET] Error: {e}")

async def test_mvp_sin(motor_manager):
    ## POC sinusoidal mouvement
    start_time=time.time()
    amp=2000
    speed=0.1
    phase=0
    await motor_manager.mvp(12,0,0,0)
    await motor_manager.mvp(13, 0,0,0)
    await motor_manager.sap(12, 138,2)
    await motor_manager.sap(13, 138,2)
    for a in range(160):
        await asyncio.sleep(1/44)
        t=time.time()-start_time
        v=(amp*math.sin(2*math.pi*speed*t+phase))
        logging.debug(v)
        await motor_manager.mvp(12, 0,0,int(v))
        await motor_manager.mvp(13, 0,0,int(v))
    await motor_manager.mvp(12,0,0,0)
    await motor_manager.mvp(13, 0,0,0)
    await asyncio.sleep(1)
    await motor_manager.sap(12, 138,0)
    await motor_manager.sap(13, 138,0)
    start_time=time.time()
    for b in range(160):
        await asyncio.sleep(1/44)
        t=time.time()-start_time
        v=(amp*math.sin(2*math.pi*speed*t+phase))
        logging.debug(v)
        await motor_manager.mvp(12, 0,0,int(v))
        await motor_manager.mvp(13, 0,0,int(v))
    await motor_manager.mvp(12,0,0,0)
    await motor_manager.mvp(13, 0,0,0)
    await asyncio.sleep(1)
    await motor_manager.sap(12, 138,1)
    await motor_manager.sap(13, 138,1)
    start_time=time.time()
    for c in range(160):
        await asyncio.sleep(1/44)
        t=time.time()-start_time
        v=(amp*math.sin(2*math.pi*speed*t+phase))
        logging.debug(v)
        await motor_manager.mvp(12, 0,0,int(v))
        await motor_manager.mvp(13, 0,0,int(v))

async def test_ror_rol_sin(motor_manager):
    start_time=time.time()
    amp=50
    speed=0.1
    phase=0
    for a in range(160*4):
        await asyncio.sleep(1/44)
        t=time.time()-start_time
        v=(amp*math.sin(2*math.pi*speed*t+phase))
        logging.debug(v)
        await motor_manager.ror(13,int(v))
        await motor_manager.ror(17,int(v))
    await motor_manager.mst(13)
    await motor_manager.mst(17)





async def start_motor_manager(s, acc):
    motor_manager= MotorManager(port=SERIAL_PORT, baudrate=BAUDRATE)
    web_api.motor_manager=motor_manager
    await motor_manager.start()
    await asyncio.sleep(1)
    await motor_manager.initialize(s, acc)

        
        
    



    #r= await motor_manager.gap(12,140)
    #logging.info(r)

async def start_api():
    config =uvicorn.Config(web_api.app, host=API_IP, port=API_PORT, log_level="debug")
    server = uvicorn.Server(config)
    #loop = asyncio.get_running_loop()
    #await loop.run_in_executor(None, server.run)
    await server.serve()

async def main():
    await asyncio.gather(start_api(), start_motor_manager(S, ACC), artnet_listener())

if __name__ == "__main__":
    #clear terminal
    utils.clear()
    if os.name=="nt":
        console.print("THIS PROGRAM IS NOT DEVELOPPED FOR WINDOWS\nit may not work as intended\nThis program has been developped and tested for Debian/Rasbian Linux systems\n", style="bold red", justify="center")
    #print cool stuff
    utils.art()
    #define command line flags and help
    parser=argparse.ArgumentParser('')
    parser.add_argument("-ap",
                        "--artnet_port",
                        type=int,
                        default=6454,
                        help="ArtNet listening port, by default it commonly set on 6454")
    parser.add_argument("-ai",
                        "--artnet_ip",
                        type=str,
                        default="192.168.1.100",
                        help="ArtNet listening IP address")
    parser.add_argument("-sp",
                        "--serial_port",
                        type=str,
                        default='/dev/ttyUSB0',
                        help="Serial port use to communicate with the Motors")
    parser.add_argument("-br",
                        "--baudrate",
                        type=int,
                        default=115200,
                        help="Baudrate use for serial communication")
    parser.add_argument("-i",
                        "--api_ip",
                        type=str,
                        default="0.0.0.0",
                        help="IP where FastAPI will send and receive messages")
    parser.add_argument("-p",
                        "--api_port",
                        type=int,
                        default=8000,
                        help="Port where FastAPI will send and receive messages")
    parser.add_argument("-v",
                        "--verbose",
                        action="store_true",
                        default=False,
                        help="If used, switch to debugging log")
    parser.add_argument("-s",
                        "--speed",
                        type=int,
                        default=1000,
                        help="Set the default speed for motion command like GOTOPOSITION (MVP).")
    parser.add_argument("-a",
                        "--acceleration",
                        type=int,
                        default=1000,
                        help="Set the default acceleration for all motion command")
    args = parser.parse_args()
    #define logging mode (verbose for full log, or default user-friendly)
    utils.verbose_mode(args.verbose)
    #define constants:
    ARTNET_PORT=args.artnet_port
    ARTNET_IP=args.artnet_ip
    SERIAL_PORT=args.serial_port
    BAUDRATE=args.baudrate
    API_IP=args.api_ip
    API_PORT=args.api_port
    S=args.speed
    ACC=args.acceleration

    


    asyncio.run(main())
