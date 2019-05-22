from builtins import str
from builtins import object
__author__ = "Mario Lukas"
__copyright__ = "Copyright 2017"
__license__ = "GPL v2"
__maintainer__ = "Mario Lukas"
__email__ = "info@mariolukas.de"

import os
import glob
import serial
import time
import logging
import threading
from fabscan.lib.util.FSUtil import FSSystem
from fabscan.lib.util.FSInject import inject
from fabscan.FSConfig import ConfigInterface


@inject(
    config=ConfigInterface
)
class FSSerialCom(object):
    def __init__(self, config):

        self.config = config

        self._logger = logging.getLogger(__name__)

        if hasattr(self.config.serial, 'port'):
            self._port = self.config.serial.port
            self._logger.debug("Port in Config found")
        else:
            self._port = "/dev/ttyAMA0"

        if hasattr(self.config.serial, 'flash_baudrate'):
            self.flash_baudrate = self.config.serial.flash_baudrate
        else:
            self.flash_baudrate = 57600

        self._baudrate = self.config.serial.baudrate
        self._serial = None
        self._connected = False
        self._firmware_version = None
        self._openSerial()
        self._logger.debug("Connection baudrate is: "+str(self._baudrate))
        self._logger.debug("Firmware flashing baudrate is: "+str(self.flash_baudrate))
        self.lock = threading.RLock()
        self._stop = False

    def avr_device_is_available(self):
        status = FSSystem.run_command("sudo avrdude-autoreset -p m328p -b "+str(self.flash_baudrate)+" -carduino -P"+str(self._port))
        return status == 0

    def avr_flash(self, fname):
        FSSystem.run_command("wc -l "+str(fname))
        status = FSSystem.run_command("sudo avrdude-autoreset -D -V -U flash:w:"+str(fname)+":i -b "+str(self.flash_baudrate)+" -carduino -pm328p -P"+str(self._port))
        if status != 0:
            self._logger.error("Failed to flash firmware")
        return status == 0

    def _connect(self):
        self._logger.debug("Trying to connect Arduino on port: "+str(self._port))
        # open serial port
        try:
            self._serial = serial.Serial(str(self._port), int(self._baudrate), timeout=5)
            time.sleep(1)
        except:
            self._logger.error("Could not open serial port")

    def _close(self):
        self._serial.close()

    def _openSerial(self):
        basedir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
        flash_file_version = max(sorted(glob.iglob(basedir+'/firmware/'+str(self.config.serial.plattform_type)+'_*.hex'), key=os.path.getctime, reverse=True))

        flash_version_number = os.path.basename(os.path.normpath(os.path.splitext(flash_file_version.split('_', 1)[-1])[0]))

        self._logger.debug("Latest available firmware version is: "+flash_version_number)

        try:
           # check if device is available
           if self.avr_device_is_available():
                   time.sleep(0.5)
                   # try to connect to arduino
                   self._connect()

                   # if connection is opened successfully
                   if self._serial.isOpen():
                           current_version = self.checkVersion()
                           self._logger.debug("Installed firmware version: "+current_version)
                           # check if autoflash is active
                           if self.config.serial.autoflash == "True":
                               ## check if firmware is up to date, if not flash new firmware
                               if not current_version == flash_version_number:
                                   self._close()
                                   self._logger.info("Old or no firmare detected trying to flash current firmware...")
                                   if self.avr_flash(flash_file_version):
                                        time.sleep(0.5)
                                        self._connect()
                                        current_version = self.checkVersion()
                                        self._logger.info("Successfully flashed new Firmware Version: "+current_version)


                   # no firmware is installed, flash firmware
                   else:
                            # if auto flash is activated
                            if self.config.serial.autoflash == "True":
                                    self._logger.info("No firmware detected trying to flash firmware...")
                                    if self.avr_flash(flash_file_version):
                                        time.sleep(0.5)
                                        self._connect()
                                        current_version = self.checkVersion()
                                        self._logger.info("Successfully flashed Firmware Version: "+current_version)
           else:
                    self._logger.error("No FabScanPi HAT or compatible device found on port "+str(self._port))

           # set connection states and version
           if self._serial.isOpen() and (current_version != "None"):
                  self._logger.info("FabScanPi is connected to FabScanPi HAT or compatible on port: "+str(self._port))
                  current_version = self.checkVersion()
                  self._firmware_version = current_version
                  self._connected = True
           else:
                  self._logger.error("Can not find Arduino or FabScanPi HAT")
                  self._connected = False

        except:
            self._logger.error("Fatal FabScanPi HAT or compatible connection error....")

    def checkVersion(self):
        if self._serial:
            try:
                self._serial.write("\r\n\r\n")
                time.sleep(2) # Wait for FabScan to initialize
                self._serial.flushInput() # Flush startup text in serial input
                self.send("M200;")
                self._serial.readline();
                # receive version number
                value = self._serial.readline()
                value = value.strip()
                if value != "":
                    return value
                else:
                    return "None"
            except Exception as e:
                self._logger.error(e)
        else:
            return "None"

    def send_and_receive(self, message):
        self.send(message)
       # time.sleep(0.2)
        response = ""
        self._stop = False
        with self.lock:
            while not self._stop:
                response += self._serial.read()
                if ">" in response:
                    response = response.rstrip(">")
                    response = response.translate(None, '\n\t\r')
                    if response:
                        self._logger.debug("Command successfully sent: " + response)
                        self._stop = True
                    break

    def flush(self):
       self._serial.flushInput()
       self._serial.flushOutput()

    def send(self, message):
        try:
            self._serial.write(message + "\n")
        except Exception as e:
            self._logger.error(e)


    def is_connected(self):
        return self._connected

    def get_firmware_version(self):
        return self._firmware_version