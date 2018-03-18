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
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
#  02110-1301, USA.
"""
This mux will only use one device and not mix it with any other input.
"""
import logging

from . import InputMux

__author__ = 'Bitcraze AB'
__all__ = ['NoMux']

logger = logging.getLogger(__name__)


class NoMux(InputMux):

    def __init__(self, *args):
        super(NoMux, self).__init__(*args)
        self.name = "Normal"
        self.role_devs = {"Device": None}

    def read(self):
####        logger.info("DDD dans nomux.read device {}".format(self.role_devs["Device"].name)) ####OK jusque là
        if self.role_devs["Device"]:
            data = self.role_devs["Device"].read() ####include_raw=True
####            logger.info("In nomux input values {}".format(data.roll)) #### 

            return data
        else:
            return None
