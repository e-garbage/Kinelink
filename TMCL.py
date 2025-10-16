import asyncio
import serial_asyncio
import logging
from rich.text import Text
import struct

"""

TMCL asynchronous command library and protocol
Written by e-garbage for STRUCTURALS, 2025

Defines most motion command available in TMCL protocol .
Designed and intended to be used mostly with TMCM-1161.
Usage with other TMCL compatible devices is not guarantee
Please be careful in your code while using this library,
motors can have unexpected behaviour if commands are wrongly invoked.

More details about TMCL and TMCM-1161 here:
https://www.analog.com/media/en/dsp-documentation/software-manuals/TMCM-1161-TMCL_firmware_manual_fw1.46_rev1.11.pdf


"""
logger = logging.getLogger(__name__)
timeout=0.1

class MotorProtocol(asyncio.Protocol):
    def __init__(self, motor_manager):
        self.motor_manager = motor_manager
        self.transport = None
        self.buffer =bytearray()
        self.response_future =None
        self._send_lock = asyncio.Lock()

    def print_packet(packet: bytes, direction: str) -> str:
        hex_str = "".join(f"{b:02X}" for b in packet)
        style = "bold green" if direction == "TX" else "bold blue"
        return(Text(f"[{style}]{direction}: {hex_str}[/{style}]"))

    def connection_made(self, transport):
        self.transport = transport
        logging.info("Serial connection established")
    
    def data_received(self, data):
        self.buffer += data
        # TMCL responses are always 9 bytes long

        #if len(self.buffer) >= 9:
        while len(self.buffer) >=9:
            packet = self.buffer[:9]   # Get one packet
            self.buffer = self.buffer[9:]  # Keep the rest (if multiple packets arrive)
            del self.buffer[:9]
            logging.debug(MotorProtocol.print_packet(packet,"RX"))
            try:
                parsed = MotorManager.parse_tmcl_response(packet, packet[1], packet[3])
                if self.response_future and not self.response_future.done():
                    self.response_future.set_result(parsed)
            except Exception as e:
                if self.response_future and not self.response_future.done():
                    self.response_future.set_exception(e)
                    logging.error(f"Failed to parse TMCL frame: {e}")

    def connection_lost(self, exc):
        logging.info("Serial connection lost")
        if self.response_future and not self.response_future.done():
            self.response_future.set_exception(exc or ConnectionError("Serial connection lost"))
        self.transport = None
        
    async def send_command(self, command, future):
        async with self._send_lock:
            self.buffer.clear()
            self.response_future = future
            self.transport.write(command)
            logging.debug(MotorProtocol.print_packet(command, "TX"))

            try:
                # Timeout handled here
                return await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError:
                logging.debug(f"Command timed out after {timeout}s")
                if not future.done():
                    future.set_exception(asyncio.TimeoutError())
                return None
            except Exception as e:
                logging.error(f"Command failed: {e}")
                if not future.done():
                    future.set_exception(e)
                return None
            finally:
                self.response_future = None

class MotorManager:
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, default_speed=100, default_accel=100, default_maxpos=5000):
        """
            TMCL command class, defines all motion command as well as command builder, serial packet builder, command sender, response parser.
            It also includes a Scanner to automatically detect available motors through the serial interface.
        """
        self.port = port
        self.baudrate = baudrate
        self.protocol = None
        self.connected={}
        self.default_speed = default_speed
        self.default_accel = default_accel
        self.default_maxpos = default_maxpos
        self.command_queue = asyncio.Queue()
        self.motor_queues={}

    async def initialize(self,s, acc):
        logging.info("Initializing connected motors - Setting up current position as home")
        await self.scan()
        logging.info(f"Scan complete - found {len(self.connected)}")
        for a in self.connected:
            try:
                await self.mst(a) #stop any ongoing motion for safety reasons
                await self.sap(a,1,0)  #set current position as Home (0)
                await self.sap(a, 4, s) # set max speed as s
                await self.sap(a, 5, acc) #set max accel
                q = asyncio.Queue(maxsize=1)  # Only keep the latest command
                self.motor_queues[a] = q
                asyncio.create_task(self._motor_worker(a, q))


            except Exception as e:
                logging.error(f"Failed to initialize default positionm motor {a}: {e}")

        logging.info("Initialization complete")

    async def start(self):
        loop = asyncio.get_running_loop()
        transport, protocol = await serial_asyncio.create_serial_connection(
            loop,
            lambda: MotorProtocol(self),
            self.port,
            baudrate=self.baudrate
        )
        self.transport = transport
        self.protocol = protocol

        # Start the background worker that sends TMCL commands
        asyncio.create_task(self._serial_worker())

    async def _serial_worker(self):
        logging.debug("_serial_worker")
        while True:
            command, future = await self.command_queue.get()
            if self.transport:
                await self.protocol.send_command(command, future)
            else:
                future.set_exception(RuntimeError("No transport available"))
            await asyncio.sleep(0.005)

    async def _motor_worker(self, addr, queue):
        """Sequential command executor per motor."""
        while True:
            cmd, args = await queue.get()
            try:
                await cmd(*args)
            except Exception as e:
                logging.warning(f"Motor {addr} worker error: {e}")
            finally:
                queue.task_done()

    def tmcl_packet_builder(self, addr:int, cmd:int, typ:int, bank:int, value:int):
        """
        Build a valid 9-bytes TMCL response frame.

        Args:
            addr = module address code (0-255)
            cmd = command code number
            typ = type number
            bank = bank or motor number
            value = Value (MSB first)
        Returns:
            a complete TMCL frame including the checksum byte with the following structure:

            Bytes   Meaning
            1       Module address
            1       Command number
            1       Type number
            1       Motor or Bank number
            4       Value(MSB first)
            1       Checksum
        
        """
        data = bytearray(9)
        data[0:8]= struct.pack('>BBBBi', addr, cmd, typ, bank, value)
        checksum =sum(data[0:8]) & 0XFF
        data[8] = checksum
        return data  

    def parse_tmcl_response(resp: bytes, expected_addr: int, expected_cmd: int):
        """
        Parse and validate a 9-byte TMCL response frame.

        Args:
            resp: The 9-byte raw response from the motor.
            expected_addr: The module address you sent the command to.
            expected_cmd: The command number you sent.

        Returns:
            A tuple: (status_code, value), or raises Exception if invalid.

        TMCL reply format:
            Every time a command has been sent to a module, the module sends a reply. The reply format with RS-232, RS-485, RS-422 and USB is as follows:

            Bytes   Meaning
            1       Reply address
            1       Module address
            1       Status (e.g. 100 means no error)
            1       Command number
            4       Value (MSB first)
            1       Checksum
        """
        if len(resp) != 9:
            logging.error(f"Invalid TMCL response length: expected 9, got {len(resp)}")
            return None

        reply_addr, addr, status, cmd = resp[0], resp[1], resp[2], resp[3]

        status_messages = {
            1:  "Wrong checksum",
            2:  "Invalid command",
            3:  "Wrong type",
            4:  "Invalid value",
            5:  "Configuration EEPROM locked",
            6:  "Command not available",
            101: "Command loaded into TMCL program EEPROM"
        }

        if status == 100:
            logging.info(f"{status} - TMCL command {cmd} executed successfully")
        elif status in status_messages:
            logging.error(status_messages[status])
            return None

        if addr != expected_addr:
            logging.error(f"Unexpected module address: expected {expected_addr}, got {addr}")
            return None

        if cmd != expected_cmd:
            logging.error(f"Unexpected command echo: expected {expected_cmd}, got {cmd}")
            return None

        checksum = sum(resp[0:8]) & 0xFF
        if checksum != resp[8]:
            logging.error(f"Checksum mismatch: calculated {checksum:#02x}, received {resp[8]:#02x}")
            return None

        value = struct.unpack_from('>i', resp, 4)[0]
        return reply_addr, addr, status, cmd, value

    async def scan(self):
        logging.info(f"Scanning available TMCL motors over {self.port}")
        found = {}
        for addr in range(255):
            await asyncio.sleep(timeout)
            try:
                resp = await self.gio(addr, 9, 1) # temperature query
                if resp is not None:
                    resp[1] == addr  # addr check after parse
                    #found.append(addr)
                    found[addr] = {"speed":self.default_speed, "accel":self.default_accel, "maxpos": self.default_maxpos}
                    logging.info(f"Motor found at address {addr} at {resp[4]}°C")
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logging.debug(f"No motor at address {addr}: {e}")
        self.connected = found
        return found

    async def tmcl_command_builder (self, addr:int, cmd:int, param:int, bank:int, value:int, name:str="TMCL"):
        command=self.tmcl_packet_builder(addr,cmd,param,bank,value)
        future= asyncio.get_event_loop().create_future()
        await self.command_queue.put((command, future))
        logging.debug(f"{name} {cmd} -> addr:{addr}, param:{param}, bank:{bank}, val:{value}")
        r = await self.protocol.send_command(command, future)
        return r
        
## TMCL COMMAND DEFINITION

    async def ror(self, addr:int, vel:int):
        """
            Rotate right with specified velocity
            Args: addr = module address, vel= velocity
            TMCL ROR command (1)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=1,param=0,bank=0,value=vel,name="ROR")

    async def rol(self, addr:int, vel:int):
        """
            Rotate left with specified velocity
            Args: addr = module address, vel= velocity
            TMCL ROL command (2)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=2,param=0,bank=0,value=vel,name="ROL")

    async def mst(self, addr:int):
        """ Stop motor movement
            Args: addr = module address
            TMCL MST command (3)"""
        return await self.tmcl_command_builder(addr=addr, cmd=3,param=0,bank=0,value=0,name="MST")
 
    async def mvp (self, addr:int, param:int, bank:int, value:int):
        """
            With this command the motor will be instructed to move to a specified relative or absolute position. It will use the acceleration/deceleration ramp and the positioning speed programmed into the unit. This command is non-blocking - that is, a reply will be sent immediately after command interpretation and initialization of the motion controller. Further commands may follow without waiting for the motor reaching its end position. The maximum velocity and acceleration as well as other ramp parameters are defined by the appropriate axis parameters. For a list of these parameters please refer to section 4. The range of the MVP command is 32 bit signed (-2147483648. . . 2147483647). Positioning can be interrupted using MST, ROL or ROR commands. Three operation types are available:
                • Moving to an absolute position in the range from -2147483648. . . 2147483647 (−231...231 − 1).
                • Starting a relative movement by means of an offset to the actual position. In this case, the new resulting position value must not exceed the above mentioned limits, too.
                • Moving the motor to a (previously stored) coordinate (refer to SCO for details).

            Args: addr = module address,
                param= 
                0= ABS (absolute), bank =0, value = position
                1= REL (relative), bank=0 value = offset
                2= COORD (go to coordinate), bank = 0...255, value= coordinate number (0..20)
            TMCL SGP command (4)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=4,param=param,bank=bank,value=value,name="MVP")

    async def sap(self, addr:int, param:int, value:int):
        """
            Set axis parameter (motion control specific settings)
            Args: addr = module address, param= type of instruction, value= intendent value of the paramater
            TMCL SAP command (5)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=5,param=param,bank=0,value=value,name="SAP")

    async def gap(self, addr:int, param:int):
        """
            Get axis parameter (motion control specific settings)
            Args: addr = module address, param= type of instruction
            TMCL GAP command (6)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=6,param=param,bank=0,value=0,name="GAP")

    async def stap(self, addr:int, param:int):
        """
            This command is used to store TMCL axis parameters permanently in the EEPROM of the module. This command is mainly needed to store the default configuration of the module. The contents of the user variables can either be automatically or manually restored at power on.
            Args: addr = module address, param= type of instruction
            TMCL STAP command (7)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=7,param=param,bank=0,value=0,name="STAP")

    async def rsap(self, addr:int, param:int):
        """
            With this command the contents of an axis parameter can be restored from the EEPROM. By default, all axis parameters are automatically restored after power up. An axis parameter that has been changed before can be reset to the stored value by this instruction.
            Args: addr = module address, param= type of instruction
            TMCL RSAP command (8)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=8,param=param,bank=0,value=0,name="RSAP")  

    async def sgp(self, addr:int, param:int, bank:int, value:int):
        """
            With this command most of the module specific parameters not directly related to motion control can be specified and the TMCL user variables can be changed. Global parameters are related to the host interface, peripherals or application specific variables. The different groups of these parameters are organized in banks to allow a larger total number for future products. Currently, bank 0 is used for global parameters, and bank 2 is used for user variables. Bank 3 is used for interrupt configuration. All module settings in bank 0 will automatically be stored in non-volatile memory (EEPROM).
            Args: addr = module address, param= type of instruction, bank= motor bank 0/2/3, value= Value of parameter
            TMCL SGP command (9)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=9,param=param,bank=bank,value=value,name="SGP")

    async def ggp(self, addr:int, param:int, bank:int):
        """
            All global parameters can be read with this function. Global parameters are related to the host interface, peripherals or application specific variables. The different groups of these parameters are organized in banks to allow a larger total number for future products. Currently, bank 0 is used for global parameters, and bank 2 is used for user variables. Bank 3 is used for interrupt configuration.
            Args: addr = module address, param= type of instruction, bank= motor bank 0/2/3,
            TMCL GGP command (10)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=10,param=param,bank=bank,value=0,name="GGP")

    async def stgp(self, addr:int, param:int):
        """
            This command is used to store TMCL global parameters permanently in the EEPROM of the module. This command is mainly needed to store the TMCL user variables (located in bank 2) in the EEPROM of the module, as most other global parameters (located in bank 0) are stored automatically when being modified. The contents of the user variables can either be automatically or manually restored at power on.
            Args: addr = module address, param= type of instruction
            TMCL STGP command (11)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=11,param=param,bank=2,value=0,name="STGP")

    async def rsgp(self, addr:int, param:int):
        """
            With this command the contents of a TMCL user variable can be restored from the EEPROM. By default, all user variables are automatically restored after power up. A user variable that has been changed before can be reset to the stored value by this instruction.
            Args: addr = module address, param= type of instruction
            TMCL RSGP command (12)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=12,param=param,bank=2,value=0,name="RSGP")

    async def rfs(self, addr:int, param:int):
        """
            The TMCM-1161 has a built-in reference search algorithm. The reference search algorithm provides different refrence search modes. This command starts or stops the built-in reference search algorithm. The status of the reference search can also be queried to see if it already has finished. (In a TMCL program it mostly is better to use the WAIT RFS command to wait for the end of a reference search.) Please see the appropriate parameters in the axis parameter table to configure the reference search algorithm to meet your needs 
            Args: addr = module address,
                param
                    0 = START - start reference search
                    1 = STOP - stop reference search
                    2 = STATUS - get reference search status

            TMCL RFS command (13)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=13,param=param,bank=0,value=0,name="RFS")

    async def sio(self, addr:int, param:int, value:int):
        """
            This command sets the states of the general purpose digital outputs.
            Args: addr = module address,param = Port number, bank =2, value = 0 or 1

            TMCL SIO command (14)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=14,param=param,bank=2,value=value,name="SIO")

    async def gio(self, addr:int, param:int, bank:int):
        """
            With this command the status of the available general purpose outputs of the module can be read. The function reads a digital or an analog input port. Digital lines will read as 0 or 1, while the ADC channels deliver their 12 bit result in the range of 0. . . 4095. In standalone mode the requested value is copied to the accumulator register for further processing purposes such as conditional jumps. In direct mode the value is only output in the value field of the reply, without affecting the accumulator. The actual status of a digital output line can also be read.
            Args: addr = module address, param = Port number, bank =0/1/2

            TMCL GIO command (15)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=15,param=param,bank=bank,value=0,name="GIO")
    
    async def wait(self, addr:int, param:int, bank:int,value:int):
        """
            This instruction interrupts the execution of the TMCL program until the specified condition is met. This command is intended for standalone operation only. There are five different wait conditions that can be used:

                    • TICKS: Wait until the number of timer ticks specified by the <ticks> parameter has been reached.
                    • POS: Wait until the target position of the motor specified by the <motor> parameter has been reached. An optional timeout value (0 for no timeout) must be specified by the <ticks> parameter.
                    • REFSW: Wait until the reference switch of the motor specified by the <motor> parameter has been triggered. An optional timeout value (0 for no timeout) must be specified by the <ticks> parameter.
                    • LIMSW: Wait until a limit switch of the motor specified by the <motor> parameter has been triggered. An optional timeout value (0 for no timeout) must be specified by the <ticks> parameter.
                    • RFS: Wait until the reference search of the motor specified by the <motor> field has been reached. An optional timeout value (0 for no timeout) must be specified by the <ticks> parameter.

            Special case for the <ticks> parameter: When this parameter is set to -1 the contents of the accumulator register will be taken for this value. So for example WAIT TICKS, 0, -1 will wait as long as specified by the value store in the accumulator. The accumulator must not contain a negative value when using this option. The timeout flag (ETO) will be set after a timeout limit has been reached. You can then use a JC ETO command to check for such errors or clear the error using the CLE command.

            Args: addr = module address, 
                param = 
                    0 = TICKS - set a timer . bank=0 , value = number of ticks to wait (1 tick = 10 millisec)
                    1 = POS - target position reached, bank = motor number, value = number of ticks to wait (0 for no timeout)
                    2 = REFSW - reference switch, bank = motor number, value = number of ticks to wait (0 for no timeout)
                    3 = LIMSW - limit switch, bank = motor number, value = number of ticks to wait (0 for no timeout)
                    4 = RFS - reference search completed, bank = motor number, value = number of ticks to wait (0 for no timeout)

            TMCL WAIT command (27)
        """
        return await self.tmcl_command_builder(addr=addr, cmd=27,param=param,bank=bank,value=value,name="WAIT")

    
