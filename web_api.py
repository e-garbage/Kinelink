from fastapi import FastAPI, Query, Request
from TMCL import MotorManager
from artnet import ArtNetProtocol
from pathlib import Path
import logging
import os, json
from telegramnotif import initialize_telegram_notifier, get_telegram_notifier

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "configs"
os.makedirs(CONFIG_DIR, exist_ok=True)
app = FastAPI(
    title="Kinelink",
    description="Kinelink API",
    version=1
)

motor_manager: MotorManager | None = None
artnet_protocol: ArtNetProtocol | None = None
top_speed=1000 ### TMCL motors allows speed from 1 to 2047, for safety reason it can be limited here to avoid crazy behaviour due to internet loss or bugs
top_accel=1000 ### Same as top speed, top accel in TMCL is in the range of 1 to 2047, but limited here for safety reasons

""" telegram_notifier = initialize_telegram_notifier(
    bot_token="8510225780:AAEb1whfYLUgXxCHVPPF5fnUgdzmcdsmZsE",  # Replace with actual token
    chat_id="-5097806322",       # Replace with actual chat ID
    motor_manager=motor_manager
) """

@app.on_event("startup") ######### on_event deprecated, change for lifespan if possible (check)
async def startup_event():
    logging.debug("FastAPI web API started")


#motor motion commands
@app.get("/m/right", description="Rotate right with specified velocity. Args: addr = module address, vel= velocity. TMCL ROR command (2)")
async def m_right(
    addr: int = Query(..., description="Module (motor) Address 0-255"),
    speed: int = Query(..., description=f"Speed 0-{top_speed}")
    ):
    e:str|None=None
    if not (1<=speed<=top_speed):
        speed=50
        e=(e or "")+f"Wrong input speed. speed set to {speed}. "
    if not (0<=addr<=255):
        addr=0
        e=(e or "")+f"Wrong input address. address set to {addr}. "
    reply = await motor_manager.ror(addr,speed)
    return {"call from":"m_right","reply":reply, "api error":e}

@app.get("/m/left", description="Rotate left with specified velocity. Args: addr = module address, vel= velocity. TMCL ROL command (3)")
async def m_left(
    addr: int = Query(..., description="Module (motor) Address 0-255"),
    speed: int = Query(..., description=f"Speed 0-{top_speed}")
    ):
    e:str|None=None
    if not (1<=speed<=top_speed):
        speed=50
        e=(e or "")+f"Wrong input speed. speed set to {speed}. "
    if not (0<=addr<=255):
        addr=0
        e=(e or "")+f"Wrong input address. address set to {addr}. "
    reply = await motor_manager.rol(addr,speed)
    return {"call from":"m_left","reply":reply, "api error":e}

@app.get("/m/stop", description="Stop motor movement. Args: addr = module address. TMCL MST command (4)")
async def m_stop(
        addr: int = Query(..., description="Module (motor) Address 0-255")
        ):
    e:str|None=None
    if not (0<=addr<=255):
        addr=0
        e=(e or "")+f"Wrong input address. address set to {addr}. "    
    reply = await motor_manager.mst(addr)
    return {"call from":"m_stop","reply":reply, "api error":e}

@app.get("/m/setref", description="Set actual position as reference point (0) Using the TMCL SAP (set axis parameter). Args: addr = module address")
async def m_setref(
    addr: int = Query(..., description="Module (motor) Address 0-255")):
    e:str|None=None
    if not (0<=addr<=255):
        addr=0
        e=(e or "")+f"Wrong input address. address set to {addr}. " 
    reply = await motor_manager.sap(addr,1,0)
    return {"call from":"m_setref","reply":reply, "api error":e}

@app.get("/m/gotopos", description="Go to a relative position")
async def m_gotopos(
    addr: int = Query(..., description="Module (motor) Address 0-255"),
    pos: int = Query(..., description="position to go -100000 - 100000")
    ):
    e:str|None=None
    if not (-100000<=pos<=100000):
        pos=0
        e=(e or "")+f"Wrong input speed. speed set to {pos}. "
    if not (0<=addr<=255):
        addr=0
        e=(e or "")+f"Wrong input address. address set to {addr}. "
    reply = await motor_manager.mvp(addr, 0, 0, pos)
    return {"call from":"m_gotopos","reply":reply, "api error":e}

# motor parameters command
@app.get("/p/setmaxpos", description="Set maximum position possible (limit switch) using SAP command")
async def p_setmaxpos(
    addr: int = Query(..., description="Module (motor) Address 0-255"),
    pos: int = Query(..., description="position to go -100000 - 100000")
    ):
    e:str|None=None
    if not (-100000<=pos<=100000):
        pos=0
        e=(e or "")+f"Wrong input speed. speed set to {pos}. "
    if not (0<=addr<=255):
        addr=0
        e=(e or "")+f"Wrong input address. address set to {addr}. "
    motor_manager.connected[addr]["maxpos"]=int(pos)
    return {"call from":"p_setmax", "api error":e}

@app.get("/p/setmaxspeed", description="Set maximum speed for motion command like /m/gotopos using SAP command. /m/left and /m/right overides this with their speed value")
async def p_setmaxpeed(
    addr: int = Query(..., description="Module (motor) Address 0-255"),
    speed: int = Query(..., description=f"max motion Speed 0-{top_speed}")
    ):
    e:str|None=None
    if not (1<=speed<=top_speed):
        speed=motor_manager.default_maxspeed
        e=(e or "")+f"Wrong input speed. speed set to {speed}. "
    if not (0<=addr<=255):
        addr=0
        e=(e or "")+f"Wrong input address. address set to {addr}. "
    reply = await motor_manager.sap(addr, 4, speed)
    motor_manager.connected[addr]["maxspeed"]=int(speed)
    return {"call from":"p_setmaxpeed","reply":reply, "api error":e}

@app.get("/p/setminspeed", description="Set minimum speed for motion command like SAP command. This only affects gotopos commands coming from Art-Net dependency on DMX Channel 1")
async def p_setminspeed(
    addr: int = Query(..., description="Module (motor) Address 0-255"),
    speed: int = Query(..., description=f"min motion Speed 0-{top_speed}")
    ):
    e:str|None=None
    if not (1<=speed<=top_speed):
        speed=motor_manager.default_minspeed
        e=(e or "")+f"Wrong input speed. speed set to {speed}. "
    if not (0<=addr<=255):
        addr=0
        e=(e or "")+f"Wrong input address. address set to {addr}. "
    motor_manager.connected[addr]["minspeed"]=int(speed)
    return {"call from":"p_setminpeed", "api error":e}

@app.get("/p/setaccel", description="Set maximum acceleration for motion command like /m/gotopos using SAP command.")
async def p_setaccel(
    addr: int = Query(..., description="Module (motor) Address 0-255"),
    accel: int = Query(..., description=f"max acceleration 1-{top_accel}")
    ):
    e:str|None=None
    if not (1<=accel<=top_speed):
        accel=50
        e=(e or "")+f"Wrong input speed. speed set to {accel}. "
    if not (0<=addr<=255):
        addr=0
        e=(e or "")+f"Wrong input address. address set to {addr}. "
    reply = await motor_manager.sap(addr, 5, accel)
    motor_manager.connected[addr]["accel"] = int(accel)
    return {"call from":"p_setaccel","reply":reply, "api error":e}

@app.get("/p/gettemp", description="Get temperature of a given motor using GIO command.")
async def p_gettemp(
    addr: int = Query(..., description="Module (motor) Address 0-255"),
    ):
    e:str|None=None
    if not (0<=addr<=255):
        addr=0
        e=(e or "")+f"Wrong input address. address set to {addr}. "
    reply = await motor_manager.gio(addr,9,1)
    return {"call from":"p_gettemp","reply":reply, "api error":e}

@app.get("/p/getpos", description="Get position of a given motor using GAP command.")
async def p_getpos(
    addr: int = Query(..., description="Module (motor) Address 0-255"),
    ):
    e:str|None=None
    if not (0<=addr<=255):
        addr=0
        e=(e or "")+f"Wrong input address. address set to {addr}. "
    reply = await motor_manager.gap(addr,1)
    return {"call from":"p_getpos","reply":reply, "api error":e}

@app.get("/p/panic", description="stop all motors between 0 to 255 with MST command")
async def p_panic():
    artnet_protocol.disable()
    reply = await motor_manager.panic()
    return{"call from":"p_panic","reply":reply}
    """ for i in range(0,256):
        await motor_manager.mst(i)
    return {"call from":"p_panic"} """

@app.get("/p/set_artnet", description="Switch between True and False in order to Activate or Deactivate Art-net input, and respond with current state")
async def p_set_artnet():
    if artnet_protocol.enabled == True:
        artnet_protocol.disable()
        r=False
    else:
        artnet_protocol.enable()
        r=True
    return {"call from":"p_set_artnet","reply":r}

@app.get("/p/get_artnet", description="Gives artnet input status either True for Active or False for Deactivated")
async def p_get_artnet():
    r= artnet_protocol.enabled
    return{"call from":"p_get_artnet","reply":r}

@app.get("/p/connected", description="return the number of TMCL modules (motors) connected and available after scan")
async def p_connected():
    if motor_manager is None:
        return []
    return motor_manager.connected

@app.get("/p/get_universe", description="gives the current art-net universe in use on the node")
async def p_get_universe():
    r=artnet_protocol.universe
    return {"call from":"p_get_universe","reply":r}

@app.get("/p/set_universe", description="set art-net universe in use on the node")
async def p_set_universe(
    val: int = Query(..., description="Art-Net universe value(0-1024)")
    ):
    e:str|None=None
    if not (0<=val<=1024):
        val=0
        e=(e or "")+f"Wrong input universe value. set to {val}."
    artnet_protocol.universe=val
    return {"call from":"p_set_universe","api error":e}

@app.get("/p/set_addr", description="Set a new address to a given module")
async def p_set_addr(
    current_addr: int =Query(..., description="Current module address"),
    new_addr: int = Query(...,description="New module address")
    ):
    e:str|None=None
    if not (0 <= current_addr <= 255 and 0 <= new_addr <= 255):
        e=(e or "")+f"Wrong address range with current address {current_addr} or new address {new_addr}. Both must be integers between 0 and 255."
        return {"call from":"p_set_addr","api error":e}
    reply = await motor_manager.sgp(current_addr,65,0,new_addr)
    return {"call from":"p_set_addr","reply":reply,"api error":e}


### Configuration Save and Recall

@app.get("/c/save_config", description="Save the current global configuration to file in the back-end. This configuration will be use at boot if default is set to True to set all parameters and position values to every connected modules")
async def c_save_config(
    name: str =Query(..., description="Name of the configuration file"),
    default: bool = Query(..., description="Boolean switch for default configuration on boot")
    ):
    # Validate runtime objects
    if motor_manager is None:
        return {"status": "error", "message": "motor_manager not initialized"}
    if artnet_protocol is None:
        return {"status": "error", "message": "artnet_protocol not initialized"}

    data = motor_manager.connected
    artnet_data = {"universe": artnet_protocol.universe}
    save_name = name
    is_default = default
    path = os.path.join(CONFIG_DIR, f"{save_name}.json")
    artnet_path = os.path.join(CONFIG_DIR, f"{save_name}_artnet.json")
    try:
        # write motor configuration
        with open(path, "w") as f:
            json.dump(data, f, indent=4)

        # write artnet configuration
        with open(artnet_path, "w") as f:
            json.dump(artnet_data, f, indent=4)

        if is_default:
            default_path = os.path.join(CONFIG_DIR, "default.json")
            try:
                if os.path.exists(default_path) or os.path.islink(default_path):
                    os.remove(default_path)
            except Exception:
                pass
            os.symlink(path, default_path)

            default_artnet = os.path.join(CONFIG_DIR, "default_artnet.json")
            try:
                if os.path.exists(default_artnet) or os.path.islink(default_artnet):
                    os.remove(default_artnet)
            except Exception:
                pass
            os.symlink(artnet_path, default_artnet)

        return {"status": "ok", "message": f"Configuration saved as '{save_name}'"}
    except Exception as e:
        return {"status": "error", "message": str(e)}




## Utility functions

@app.get("/p/version", description="Return application version")
async def p_version():
    return {"version": getattr(app.state, "version", None)}

""" @app.get("/n/enable", description="enable telegram notifications")
async def n_enable():
    try:
        telegram_notifier.enable_notifications()
        return{"call from":"n_enable", "reply":"notifications enabled"}
    except Exception as e:
        return{"call from":"n_enable", "reply":e}

@app.get("/n/disable", description="disable telegram notifications")
async def n_disable():
    try:
        telegram_notifier.disable_notifications()
        return{"call from":"n_disable", "reply":"notifications disabled"}
    except Exception as e:
        return{"call from":"n_disable", "reply":e}

@app.get("/n/interval", description="set notification intervals")
async def set_notification_interval(val: int):
    try:
        telegram_notifier.set_interval(val)
        return {"status": "success", "message": f"Interval set to {val} seconds"}
    except Exception as e:
        return{"call from":"n_disable", "reply":e} """


    


## BACKLOG NOT IMPLEMENTED FEATURES YET

@app.get("/p/scan", description="scan for connected motors")
async def p_scan():
    reply = await motor_manager.scan()
    return {"call from":"p_scan", "reply":reply}

@app.get("/c/list_config")
async def list_configs():
    configs = []
    for file in os.listdir(CONFIG_DIR):
        if file.endswith(".json"):
            path = os.path.join(CONFIG_DIR, file)
            is_default = os.path.islink(path) and os.path.basename(os.readlink(path)) == "default.json"
            configs.append({
                "name": file.replace(".json", ""),
                "is_default": file == "default.json"
            })
    return configs

@app.get("/c/load_config/{name}")
async def load_config(name: str):
    path = os.path.join(CONFIG_DIR, f"{name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"No config named {name}"}
    with open(path, "r") as f:
        return json.load(f)
    
@app.delete("/c/delete_config/{name}")
async def delete_config(name: str):
    path = os.path.join(CONFIG_DIR, f"{name}.json")
    if not os.path.exists(path):
        return {"status": "error", "message": f"No config named {name}"}
    os.remove(path)
    return {"status": "ok", "message": f"Deleted {name}.json"} 
