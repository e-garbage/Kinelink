from fastapi import FastAPI, Query, Request
#from fastapi.middleware.cors import CORSMiddleware
from TMCL import MotorManager
from pathlib import Path
import logging
import os, json

"""
API commands:
##tmcl motion commands
/m/left (addr, speed)
/m/right (addr, speed)
/m/stop (addr)
/m/setref (addr)
/m/gotopos (addr, pos, speed)

##tmcl parameters commands
/p/setmin (addr, pos)
/p/setmax (addr, pos)
/p/setspeed (addr, speed)
/p/setaccel (addr, accel)
/p/gettemp (addr)
/p/getstatus (addr)
/p/getid (addr)
/p/getposition (addr)
/p/panic (addr)
/scan ()

## ArtNet commands
/a/setartnetuniverse (value)
/a/setartnetport (ip)
/a/artnet_on (bool)

API request logic:
m=motor motion
p=motor parameters
a=artnet parameters

"""


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "configs"
os.makedirs(CONFIG_DIR, exist_ok=True)
app = FastAPI()


app.state.universe = 0
origins=[
    "http://localhost",
    "http://localhost:80",
    "https://localhost",
    "https://localhost:8000",
    
]
""" app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
) """
motor_manager: MotorManager | None = None
top_speed=1000 ### TMCL motors allows speed from 1 to 2047, for safety reason it can be limited here to avoid crazy behaviour due to internet loss or bugs
top_accel=1000 ### Same as top speed, top accel in TMCL is in the range of 1 to 2047, but limited here for safety reasons

universe: None

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
@app.get("/p/setmax", description="Set maximum position possible (limit switch) using SAP command")
async def p_setmax(
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

@app.get("/p/setspeed", description="Set maximum speed for motion command like /m/gotopos using SAP command. /m/left and /m/right overides this with their speed value")
async def p_setpeed(
    addr: int = Query(..., description="Module (motor) Address 0-255"),
    speed: int = Query(..., description=f"max motion Speed 0-{top_speed}")
    ):
    e:str|None=None
    if not (1<=speed<=top_speed):
        speed=50
        e=(e or "")+f"Wrong input speed. speed set to {speed}. "
    if not (0<=addr<=255):
        addr=0
        e=(e or "")+f"Wrong input address. address set to {addr}. "
    reply = await motor_manager.sap(addr, 4, speed)
    motor_manager.connected[addr]["speed"]=int(speed)
    return {"call from":"p_setpeed","reply":reply, "api error":e}

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
    for i in range(0,256):
        await motor_manager.mst(i)
    return {"call from":"p_panic"}


@app.get("/p/scan", description="scan for connected motors")
async def p_scan():
    reply = await motor_manager.scan()
    return {"call from":"p_scan", "reply":reply}

@app.get("/p/connected", description="return the number of TMCL modules (motors) connected and available after scan")
async def p_connected():
    if motor_manager is None:
        return []
    return motor_manager.connected


@app.get("/p/get_universe", description="gives the current art-net universe in use on the node")
async def p_get_universe():
    return {"universe": app.state.universe}

### Configuration Save and Recall

@app.post("/c/save_config")
async def save_config(request:Request):
    data = await request.json()
    save_name = data.get("name", "unnamed")
    is_default = data.get("default", False)
    config = data.get ("config",{})
    path = os.path.join(CONFIG_DIR, f"{save_name}.json")
    try:
        with open(path, "w") as f:
            json.dump(config, f, indent=4)
        if is_default:
            default_path =os.path.join(CONFIG_DIR, "default.json")
            if os.path.exists(default_path):
                os.remove(default_path)
            os.symlink(path, default_path)
        return{"status": "ok", "message": f"Configuration saved as '{save_name}'"}
    except Exception as e:
        return{"status":"error", "message": str(e)}
    
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
