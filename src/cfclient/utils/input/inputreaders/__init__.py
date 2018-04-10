#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#     ||          ____  _ __
#  +------+      / __ )(_) /_______________ _____  ___
#  | 0xBC |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
#  +------+    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
#   ||  ||    /_____/_/\__/\___/_/   \__,_/ /___/\___/
#
#  Copyright (C) 2014 Bitcraze AB
#
#  Crazyflie Nano Quadcopter Client
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.

#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA  02110-1301, USA.

"""
Find all the available input readers and try to import them.

To create a new input device reader drop a .py file into this
directory and it will be picked up automatically.
"""

import logging
from ..inputreaderinterface import InputReaderInterface

__author__ = 'Bitcraze AB'
__all__ = ['InputDevice']

logger = logging.getLogger(__name__)


# Forces py2exe to include the input readers in the windows build
try:
    from . import pysdl2  # noqa
    from . import linuxjsdev  # noqa
except Exception:
    pass

# Statically listing the available input readers
input_readers = ["linuxjsdev",
                 "pysdl2"]

logger.info("Input readers: {}".format(input_readers))

initialized_readers = []
available_devices = []

for reader in input_readers:
    try:
        module = __import__(reader, globals(), locals(), [reader], 1)
        main_name = getattr(module, "MODULE_MAIN")
        initialized_readers.append(getattr(module, main_name)())
        logger.info("Successfully initialized [{}]".format(reader)) ####
####        available_devices.clear()
    except Exception as e:
        logger.info("Could not initialize [{}]: {}".format(reader, e))


def devices():
    # Todo: Support rescanning and adding/removing devices
####    if len(available_devices) == 0:
####    available_devices.clear()
####    logger.info("Initialized readers")
    i = 0
####    logger.info("ici")
    for r in initialized_readers:
    
####        logger.info("Iitialized readers {}".format(r))
        devs = r.devices()
####        if len(devs) == 0 : return []
####        logger.info("iciici")
        for dev in devs :    
            keep = True
####            logger.info("A device >{}<".format(dev["name"]))
            for d in available_devices :
####                logger.info("an available device >{}<".format(d.name))
                if dev["name"] == d.name :
                    keep = False
            if keep :
####                logger.info("Keep.......")
                available_devices.append(InputDevice(dev["name"],
                                                     dev["id"],
                                                     r))
####        logger.info("par ici")
        for d in available_devices :
            lost = True
            for dev in devs :
                if dev["name"] == d.name :
                    lost = False
            if lost :
                logger.info("Lost.......")
                available_devices.remove(d)
                
####    for d in available_devices : logger.info("Dans init de input readers {}".format(available_devices)) ####
####    for d in available_devices : logger.info("Dans init de input readers {}, pas {}".format(d, i)) ####
    i+=1
####    logger.info("là")
    return available_devices


class InputDevice(InputReaderInterface):

    def __init__(self, dev_name, dev_id, dev_reader):
        super(InputDevice, self).__init__(dev_name, dev_id, dev_reader)

        # All devices supports mapping (and can be configured)
        self.supports_mapping = True

        # Limit roll/pitch/yaw/thrust for all devices
        self.limit_rp = True
        self.limit_thrust = True
        self.limit_yaw = True
        self.db = 0.

    def name(self) :
        return dev_name

    def open(self):
        # TODO: Reset data?
####        logger.info("Dans open du lecteur device n° {}".format(self.id))
        self._reader.open(self.id)

    def close(self):
####        logger.info("CCCCCCCCCCCCClose") ####
        self._reader.close(self.id)

    def set_dead_band(self, db):
        self.db = db

    def read(self, include_raw=False):

####        self._reader.read(self.id) #### Pourquoi deux lectures ?
        r = self._reader.read(self.id)
####        logger.info("sself._reader.read {}".format(r))
        if r == None : return 0

        [axis, buttons] = r ####self._reader.read(self.id)

        # To support split axis we need to zero all the axis
        self.data.reset_axes()

        i = 0
        for a in axis:
            index = "Input.AXIS-%d" % i
            try:
                if self.input_map[index]["type"] == "Input.AXIS":
                    key = self.input_map[index]["key"]
                    axisvalue = a + self.input_map[index]["offset"]
                    axisvalue = axisvalue / self.input_map[index]["scale"]
                    self.data.set(key, axisvalue + self.data.get(key))
            except (KeyError, TypeError):
                pass
            i += 1

        # Workaround for fixing issues during mapping (remapping buttons while
        # they are pressed.
        self.data.reset_buttons()

        i = 0
        for b in buttons:
            index = "Input.BUTTON-%d" % i
            try:
                if self.input_map[index]["type"] == "Input.BUTTON":
                    key = self.input_map[index]["key"]
                    self.data.set(key, True if b == 1 else False)
            except (KeyError, TypeError):
                # Button not mapped, ignore..
                pass
            i += 1

        self.data.roll = InputDevice.deadband(self.data.roll, self.db)
        self.data.pitch = InputDevice.deadband(self.data.pitch, self.db)

        if self.limit_rp:
            [self.data.roll, self.data.pitch] = self._scale_rp(self.data.roll,
                                                               self.data.pitch)
        if self.limit_thrust:
            self.data.thrust = self._limit_thrust(self.data.thrust,
                                                  self.data.assistedControl,
                                                  self.data.estop)
        if self.limit_yaw:
            self.data.yaw = self._scale_and_deadband_yaw(self.data.yaw)

        if include_raw:
            return [axis, buttons, self.data]
        else:
            return self.data

    @staticmethod
    def deadband(value, threshold):
        if abs(value) < threshold:
            value = 0
        elif value > 0:
            value -= threshold
        elif value < 0:
            value += threshold
        return value / (1 - threshold)
