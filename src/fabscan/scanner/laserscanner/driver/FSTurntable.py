from builtins import str
from builtins import object
__author__ = "Mario Lukas"
__copyright__ = "Copyright 2017"
__license__ = "GPL v2"
__maintainer__ = "Mario Lukas"
__email__ = "info@mariolukas.de"

import time
from fabscan.lib.util.FSInject import inject
from fabscan.FSConfig import ConfigInterface

@inject(
    config=ConfigInterface
)
class Turntable(object):
    def __init__(self, serial_object, config):
        self.config=config
        self.serial_connection = serial_object
        # Number of steps for the turntable to do a full rotation
        # DEFAULT Value for FS Shield is 1/16 Step
        self.steps_for_full_rotation = self.config.turntable.steps
        # scaler for silent step sticks was in firmware before.
        self.scaler = 4

    def step(self, steps, speed):
        '''
        Accepts number of steps to take
        '''
        steps *= self.scaler

        if self.serial_connection != None:
            command = "G04 T"+str(steps)+" F"+str(speed)+";"
            self.serial_connection.send_and_receive(command)

    def step_blocking(self, steps, speed):
        steps *= self.scaler

        if self.serial_connection != None:
            command = "G04 T"+str(steps)+" F"+str(speed)+";"
            self.serial_connection.send_and_receive(command)
            time.sleep(1)

    def enable_motors(self):
        if self.serial_connection != None:
            command = "M17;"
            self.serial_connection.send_and_receive(command)

    def disable_motors(self):
        if self.serial_connection != None:
            command = "M18;"
            self.serial_connection.send_and_receive(command)

    def start_turning(self):
        if self.serial_connection != None:
            self.enable_motors()
            command = "G06;"
            self.serial_connection.send_and_receive(command)

    def stop_turning(self):
        if self.serial_connection != None:
            self.disable_motors()
            command = "G07;"
            self.serial_connection.send_and_receive(command)

