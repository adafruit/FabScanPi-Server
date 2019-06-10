from builtins import str
from builtins import object

__author__ = "Mario Lukas"
__copyright__ = "Copyright 2017"
__license__ = "GPL v2"
__maintainer__ = "Mario Lukas"
__email__ = "info@mariolukas.de"
import time
import logging
from adafruit_crickit import crickit
from adafruit_seesaw.neopixel import NeoPixel

class Led(object):
    def __init__(self, serial_object):
        self._logger = logging.getLogger(__name__)
        self.pixels = NeoPixel(crickit.seesaw, 20, 12)


    def on(self, red, green, blue):
        self._logger.debug("Setting LED to (%d, %d, %d)", red, green, blue)
        self.pixels.fill((red, green, blue))

    def off(self):
        self._logger.debug("Turning LED off")
        self.pixels.fill((0, 0, 0))
