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
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "configs"

#CHANGE VERSION NUMBER HERE
version=1.4
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
    
def define_artnet_universe(arg_universe=None):
    """Return the Art-Net universe to use.

    Priority:
    1. If configs/default_artnet.json exists and contains a numeric 'universe' key -> use that.
    2. Else if arg_universe is not None -> use int(arg_universe).
    3. Else -> return 0.
    """
    default_artnet_path = os.path.join(str(CONFIG_DIR), "default_artnet.json")
    if os.path.exists(default_artnet_path) or os.path.islink(default_artnet_path):
        try:
            with open(default_artnet_path, "r") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict) and "universe" in loaded:
                try:
                    return int(loaded["universe"])
                except Exception:
                    logging.warning(f"Invalid 'universe' value in {default_artnet_path}; falling back")
            else:
                logging.warning(f"{default_artnet_path} does not contain 'universe' key; falling back")
        except Exception as e:
            logging.error(f"Failed to load default artnet config {default_artnet_path}: {e}")

    if arg_universe is not None:
        try:
            return int(arg_universe)
        except Exception:
            logging.warning("Invalid CLI artnet_universe value; falling back to 0")

    return 0

async def start_artnet(interface, port, universe, motor_manager=None):
    loop= asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ArtNetProtocol(motor_manager, universe),
        local_addr=(interface, port)
    )
    return transport, protocol 

async def start_api():
    """ web_api.app.state.univers=ARTNET_UNIVERSE """
    config =uvicorn.Config(web_api.app, host=API_IP, port=API_PORT, log_level="debug")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    motor_manager= MotorManager(port=SERIAL_PORT, baudrate=BAUDRATE, default_accel=ACC, default_maxspeed=MAXSPEED, default_minspeed=MINSPEED, module_range=MODULE_RANGE)
    web_api.motor_manager=motor_manager
    web_api.app.state.version=version
    await motor_manager.start()
    await asyncio.sleep(1)
    await motor_manager.initialize()
    transport, artnet_protocol = await start_artnet(ARTNET_IP, ARTNET_PORT,ARTNET_UNIVERSE, motor_manager)
    web_api.artnet_protocol =artnet_protocol
    web_api.app.state.motor_manager=motor_manager
    web_api.app.state.artnet=artnet_protocol
    await start_api()

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
    parser.add_argument("-maxs",
                        "--max_speed",
                        type=int,
                        default=100,
                        help="Set the default maximum speed for motion command like GOTOPOSITION (MVP) coming from art-net. This speed is used for GOTOPOSITION coming from API or debug")
    parser.add_argument("-mins",
                        "--min_speed",
                        type=int,
                        default=10,
                        help="Set the default minimum speed for motion command like GOTOPOSITION (MVP) coming from art-net.")
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
    parser.add_argument("-r",
                        "--module_range",
                        type=int,
                        default=255,
                        help="Size of the module range to scan at boot. Max is 255 due to TMCL limitations. For debug purposes mainly.")
    args = parser.parse_args()
    #define logging mode (verbose for full log, or default user-friendly)
    utils.verbose_mode(args.verbose)
    #define constants:
    ARTNET_PORT=args.artnet_port
    ARTNET_IP=args.artnet_ip
    ARTNET_UNIVERSE=define_artnet_universe()
    SERIAL_PORT=args.serial_port
    BAUDRATE=args.baudrate
    API_IP=args.api_ip
    API_PORT=args.api_port
    MAXSPEED=args.max_speed
    MINSPEED=args.min_speed
    MODULE_RANGE=args.module_range
    ACC=args.acceleration

    asyncio.run(main())
