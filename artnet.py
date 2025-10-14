
import asyncio
import logging
import struct

"""
CH1     bi (directional) mode   002-127     speed left (max speed in settings to 1)
                                128         stop (MST)
                                129-255     speed right (1 to max speed in settings)
                                000-001         channel not in use

CH2     move left               003-255     speed left (up to max speed in settings)
                                001-002     stop (MST)
                                000-001        channel not in use

CH3     move right              003-255     speed right (up to max speed in settings)
                                001-002     stop (MST)
                                000-001        channel not in use

CH4     move to                 002-255     position (0=Home position i.e position at boot; 255 max position in settings)
                                000-001        channel not in use

CH5     Homing                  002-255     go to position 0
                                000-001     channel mot in use
"""

ARTNET_HEADER = b"Art-Net\x00"
OPCODE_DMX = 0x5000  # little-endian

class utils():
    def map_value(x, src_min, src_max, dst_min, dst_max):
        if src_max - src_min == 0:
            return dst_min
        return ((x - src_min) / (src_max - src_min)) * (dst_max - dst_min) + dst_min
    
class ArtNetProtocol(asyncio.DatagramProtocol):
    def __init__(self, motor_manager=None, universe=0):
        self.motor_manager = motor_manager
        self.universe = universe
    # to use when universe is made accessible through API.
    #work in progress
    def set_universe (self, new_universe:int):
        """Dynamically update artnet universe"""
        logging.info(f"Art-Net universe changed from {self.universe} to {new_universe}")
        self.universe=new_universe

    def connection_made(self, transport):
        self.transport = transport
        logging.info(f"Art-Net listener listening on {transport.get_extra_info('sockname')}")

    def datagram_received(self, data: bytes, addr):
        if not data.startswith(ARTNET_HEADER):
            return
        opcode = struct.unpack("<H", data[8:10])[0]
        if opcode != OPCODE_DMX:
            return
        universe = struct.unpack("<H", data[14:16])[0]
        if universe != self.universe:
            return
        length = struct.unpack(">H", data[16:18])[0]
        dmx_data = data[18:18+length]
        self._process_dmx(dmx_data, self.motor_manager)

    def error_received(self, exc):
        logging.error(f"Art-Net receive error: {exc}")

    def _process_dmx(self, dmx_data: bytes, motor_manager):
        
        """
        Process incoming DMX data and trigger TMCL commands.
        Each motor consumes 5 channels:
            CH1 - bidirectional speed mode
            CH2 - move left
            CH3 - move right
            CH4 - move to absolute position
            CH5 - homing
        """
        for motor_addr, connected in motor_manager.connected.items():
            base = motor_addr-1
            if base <0 :
                continue
            if base+4 >=len(dmx_data):
                continue
            try:
                ch1, ch2, ch3, ch4, ch5 = dmx_data[base:base+5]
                maxpos = connected.get("maxpos")
                maxspeed = connected.get("speed")
                # --- CH1: Bidirectional speed ---
                if 2 <= ch1 <= 127:  # move left
                    speed = int(utils.map_value(ch1, 2,127,maxspeed, 1))
                    asyncio.create_task(motor_manager.ror(motor_addr, speed))
                elif ch1 == 128:  # stop
                    asyncio.create_task(motor_manager.mst(motor_addr))
                elif 129 <= ch1 <= 255:  # move right
                    speed = int(utils.map_value(ch1, 129,255,1, maxspeed))
                    asyncio.create_task(motor_manager.rol(motor_addr, speed))

                # --- CH2: Move left ---
                elif 3 <= ch2 <= 255:
                    speed = int(utils.map_value(ch1, 3,255,1, maxspeed))
                    asyncio.create_task(motor_manager.ror(motor_addr, speed))
                elif 1 <= ch2 <= 2:
                    asyncio.create_task(motor_manager.mst(motor_addr))

                # --- CH3: Move right ---
                elif 3 <= ch3 <= 255:
                    speed = int(utils.map_value(ch1, 3,255,1, maxspeed))
                    asyncio.create_task(motor_manager.rol(motor_addr, speed))
                elif 1 <= ch3 <= 2:
                    asyncio.create_task(motor_manager.mst(motor_addr))

                # --- CH4: Move to position ---
                if ch4 >= 2:
                    pos = int(utils.map_value(ch4, 2,255,1,maxpos ))
                    asyncio.create_task(motor_manager.mvp(motor_addr, 0, 0, pos))

                # --- CH5: Homing ---
                if ch5 >= 2:
                    asyncio.create_task(motor_manager.mvp(motor_addr, 0, 0, 0))
            except IndexError:
                continue
            except Exception as e:
                logging.warning(f"Error processing DMX for motor {motor_addr}: {e}")

