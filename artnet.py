import asyncio
import logging
import socket
import struct
from pyartnet import ArtNetNode

node=ArtNetNode('192.168.1.0', 6454)
universe=node.add_universe(0)
channel=universe.add_channel()


"""
max refresh rate in dmx512 is 44Hz
ARTNET-DMX 
CONTROL LIST

CH1     stop motion     000 - 001   
CH1     move left       002 - 255   speed
CH2     stop motion     000 - 001   
CH2     move right      002 - 255   speed
CH3     move relative   000 - 255   postion between 0 (home) and 255 (maxpos)
    CH3 motion is relative between 2 arbitrary defined positions (set)
    each received instruction should be executed in one frame (1/44 sec) with max speed capped



    move to pos at specified speed
    input are pos to move to and movement duration, output is dirtection and speed
    v=d/t

    set 0 at boot for all
    set default (12000) maxpos for all at boot

    in manual: calculation to get the actual number of step per sec for a given velocity


    vel = input_pos (motor range)/(1/44)




new channel definiton

CH1     bi (directional) mode   000-127     speed left (max speed in settings to 1)
                                128         stop (MST)
                                129-255     speed right (1 to max speed in settings)
CH2     move left               002-255     speed left (up to max speed in settings)
                                000-001     stop (MST)
CH3     move right              002-255     speed right (up to max speed in settings)
                                000-001     stop (MST)
CH4     move to                 000-255     position (0=Home position i.e position at boot; 255 max position in settings)

CH5     Homing                  000-255     go to position 0 





"""



ARTNET_PORT = 6454
ARTNET_HEADER = b"Art-Net\x00"
OPCODE_DMX = 0x5000  # little-endian in Art-Net packets

def map_value(x, src_min, src_max, dst_min, dst_max):
    if src_max - src_min == 0:
        return dst_min
    return ((x - src_min) / (src_max - src_min)) * (dst_max - dst_min) + dst_min

class ArtNetListener:
    def __init__(self, interface_ip: str, motor_manager):
        """
        interface_ip: IP of the interface to listen on (e.g. '0.0.0.0' for all)
        motor_manager: reference to your TMCL motor manager instance
        """
        self.interface_ip = interface_ip
        self.motor_manager = motor_manager
        self.transport = None

    async def start(self):
        loop = asyncio.get_running_loop()

        # Create UDP socket bound to Art-Net port
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.interface_ip, ARTNET_PORT))
        sock.setblocking(False)

        logging.info(f"Art-Net listener started on {self.interface_ip}:{ARTNET_PORT}")

        while True:
            try:
                data, addr = await loop.sock_recvfrom(sock, 1024)
                self._handle_packet(data, addr)
            except Exception as e:
                logging.error(f"Error in Art-Net listener: {e}")

    def _handle_packet(self, data: bytes, addr):
        # Basic sanity check
        if not data.startswith(ARTNET_HEADER):
            return
        
        opcode = struct.unpack("<H", data[8:10])[0]
        if opcode != OPCODE_DMX:
            return

        # DMX payload length
        length = struct.unpack(">H", data[16:18])[0]
        dmx_data = data[18:18+length]

        # Here you map DMX channels to TMCL motor commands
        self._process_dmx(dmx_data)

    def _process_dmx(self, dmx_data: bytes):
        # Example: for 50 motors, each has 1 control channel (0-49)
        for motor_addr in range(50):
            try:
                channel_value = dmx_data[motor_addr]  # DMX channels are 0-based
                if channel_value > 0:  # Only trigger if channel has data
                    # Example: Send TMCL command to set velocity
                    asyncio.create_task(
                        self.motor_manager.mst(motor_addr)  # replace with actual TMCL cmd
                    )
            except IndexError:
                pass
            except Exception as e:
                logging.warning(f"Error processing DMX for motor {motor_addr}: {e}")

    def parse_dmx(connected, channels, motor_manager, max_speed):
        commands={}

        for m in connected:
            #channel 1 bi mode
            if 0<=channels[0]<=127:
                motor_manager.ror(m, map_value(channels[0], 0, 127, max_speed, 1))
            elif channels[0]==128:
                motor_manager.mst(m)
            else:
                motor_manager.rol(m, map_value(channels[0], 129, 255,1, max_speed))
            #channel 2 move left
            if channels[1] <=1:
                motor_manager.mst(m)
            else:
                motor_manager.rol(m, map_value(channels[1], 2, 255, 1, max_speed))
            #channel 3 move left
            if channels[2] <=1:
                motor_manager.mst(m)        
