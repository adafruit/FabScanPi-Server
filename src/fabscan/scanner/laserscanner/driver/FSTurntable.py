from builtins import str
from builtins import object
__author__ = "Mario Lukas"
__copyright__ = "Copyright 2017"
__license__ = "GPL v2"
__maintainer__ = "Mario Lukas"
__email__ = "info@mariolukas.de"

import time
from adafruit_crickit import crickit
from adafruit_motor import stepper

from fabscan.lib.util.FSInject import inject
from fabscan.FSConfig import ConfigInterface

INTERSTEP_DELAY = 0.01

# @inject(
#     config=ConfigInterface
# )
class Turntable(object):
    def __init__(self, serial_object, config):
        self.config=config
        # Number of steps for the turntable to do a full rotation
        # DEFAULT Value for FS Shield is 1/16 Step
        self.steps_for_full_rotation = self.config.turntable.steps
        # scaler for silent step sticks was in firmware before.
        self.scaler = 4
        self.stepper_motor = crickit.stepper_motor

    def step(self, steps, speed):
        '''
        Accepts number of steps to take
        '''
        for i in range(steps):
            stepper_motor.onestep(direction=stepper.FORWARD)
            time.sleep(INTERSTEP_DELAY)

    def step_blocking(self, steps, speed):
        '''
        Accepts number of steps to take
        '''
        step(steps, 0)

    def enable_motors(self):
        pass

    def disable_motors(self):
        pass

    def start_turning(self):
        pass

    def stop_turning(self):
        pass
