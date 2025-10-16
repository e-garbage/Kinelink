import asyncio
import logging
from TMCL import MotorManager
from artnet import ArtNetProtocol
import web_api
import uvicorn
from rich.logging import RichHandler
from rich.console import Console
import os
import argparse


#CHANGE VERSION NUMBER HERE
version=1.1
console=Console()

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
        logging.basicConfig(level=log_mod, format=LOGGING_FORMAT, handlers=[RichHandler(rich_tracebacks=False, show_path=False, markup=True)])
    
async def start_artnet(interface, port, universe, motor_manager=None):
    loop= asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ArtNetProtocol(motor_manager, universe),
        local_addr=(interface, port)
    )    

async def start_api():
    web_api.app.state.univers=ARTNET_UNIVERSE
    config =uvicorn.Config(web_api.app, host=API_IP, port=API_PORT, log_level="debug")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    motor_manager= MotorManager(port=SERIAL_PORT, baudrate=BAUDRATE, default_accel=ACC, default_speed=S)
    web_api.motor_manager=motor_manager
    await motor_manager.start()
    await asyncio.sleep(1)
    await motor_manager.initialize(S, ACC)
    await asyncio.gather(start_api(), start_artnet(ARTNET_IP, ARTNET_PORT,ARTNET_UNIVERSE, motor_manager))

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
                        default="0.0.0.0",
                        help="ArtNet IP to listen to (ie your the control surface) default is 0.0.0.0, this means it listen to any incoming ArtNet packet")
    parser.add_argument("-au",
                        "--artnet_universe",
                        type=int,
                        default=0,
                        help="Artnet listening Universe, default 0")
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
                        default=100,
                        help="Set the default speed for motion command like GOTOPOSITION (MVP).")
    parser.add_argument("-a",
                        "--acceleration",
                        type=int,
                        default=100,
                        help="Set the default acceleration for all motion command")
    parser.add_argument("-mp",
                        "--max-pos",
                        type=int,
                        default=5000,
                        help="Maxium position use in Art-Net implementation. When reached, the motor will stop, and won't go further.")
    args = parser.parse_args()
    #define logging mode (verbose for full log, or default user-friendly)
    utils.verbose_mode(args.verbose)
    #define constants:
    ARTNET_PORT=args.artnet_port
    ARTNET_IP=args.artnet_ip
    ARTNET_UNIVERSE=args.artnet_universe
    SERIAL_PORT=args.serial_port
    BAUDRATE=args.baudrate
    API_IP=args.api_ip
    API_PORT=args.api_port
    S=args.speed
    ACC=args.acceleration

    asyncio.run(main())
