from builtins import object
__author__ = "Mario Lukas"
__copyright__ = "Copyright 2017"
__license__ = "GPL v2"
__maintainer__ = "Mario Lukas"
__email__ = "info@mariolukas.de"

from adafruit_crickit import crickit

class Laser(object):
    def __init__(self, serial_object):
        pass

    def on(self, laser=0):
        if (laser != None):
            if laser == 0:
                crickit.drive_1.fraction = 1.0
            else:
                crickit.drive_2.fraction = 1.0

    def off(self, laser=0):
        if (laser != None):
            if laser == 0:
                crickit.drive_1.fraction = 0.0
            else:
                crickit.drive_2.fraction = 0.0
