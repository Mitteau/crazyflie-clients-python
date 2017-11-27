#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#     ||          ____  _ __
#  +------+      / __ )(_) /_______________ _____  ___
#  | 0xBC |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
#  +------+    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
#   ||  ||    /_____/_/\__/\___/_/   \__,_/ /___/\___/
#
#  Copyright (C) 2011-2013 Bitcraze AB
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

#  You should have received a copy of the GNU General Public License along with
#  this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""
The console tab is used as a console for printouts from the Crazyflie.
"""

import logging

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal

import cfclient
from cfclient.ui.tab import Tab
from cflib.crtp.crtpstack import CRTPPacket
from cflib.crtp.crtpstack import CRTPPort
from cflib.crtp.crtpdriver import CRTPDriver

__author__ = 'Bitcraze AB'
__all__ = ['ConsoleTab']

logger = logging.getLogger(__name__)

dialog_tab_class = uic.loadUiType(cfclient.module_path +
                                   "/ui/tabs/dialogTab.ui")[0]


class DialogTab(Tab, dialog_tab_class):
    """Dialog tab for dialog with Crazyflie"""
    _connected_signal = pyqtSignal(str)
    _disconnected_signal = pyqtSignal(str)
    _received_pk = pyqtSignal(object)
    _sent_pk = pyqtSignal(object)

    def __init__(self, tabWidget, helper, *args):
        super(DialogTab, self).__init__(*args)
        self.setupUi(self)

        self.tabName = "Dialog"
        self.menuName = "Dialog"

        self.tabWidget = tabWidget
        self._helper = helper
        self.pk = CRTPPacket()

        # Always wrap callbacks from Crazyflie API though QT Signal/Slots
        # to avoid manipulating the UI when rendering it
        self._connected_signal.connect(self._connected)
        self._disconnected_signal.connect(self._disconnected)
        self._received_pk.connect(self.printText_in)
        self._sent_pk.connect(self.printText_out)
        self._helper.cf.connected.add_callback(self._connected_signal.emit)
        self._helper.cf.disconnected.add_callback(
            self._disconnected_signal.emit)
        self._helper.cf.packet_received.add_callback(self._received_pk.emit)
        self._helper.cf.packet_sent.add_callback(self._sent_pk.emit)
        self.line_number.activated.connect(self.change_lines)
        self.port.activated.connect(self.change_port)
        self.channel.activated.connect(self.change_channel)
        self.direction.activated.connect(self.change_direction)
        
        self.send.setEnabled(False)
        self.startButton.setEnabled(False)
        self.clearButton.clicked.connect(self.clear)
        self.the_port = -1
        self.the_channel = -1
        self.line = 0
        self.lines_max = 20
        self.the_direction = 2

    def quality(self) :
        pass

    def error(self) :
        pass

    def start(self) :
        self.line = 0

    def change_lines(self, i) :
        logger.info('Lines activated {}'.format(i))
        if i == 0 : self.lines_max = 10
        elif i == 1 : self.lines_max = 20
        elif i == 2 : self.lines_max = 80
        elif i == 3 : self.lines_max = 400
        elif i == 4 : self.lines_max = -1

    def change_port(self, i) :
        if i == 0 : self.the_port =0x0
        elif i == 1 : self.the_port = 0x1
        elif i == 2 : self.the_port = 0x2
        elif i == 3 : self.the_port = 0x3
        elif i == 4 : self.the_port = 0x4
        elif i == 5 : self.the_port = 0x5
        elif i == 6 : self.the_port = 0x6
        elif i == 7 : self.the_port = 0x7
        elif i == 8 : self.the_port = 0x8
        elif i == 9 : self.the_port = 0x9
        elif i == 10 : self.the_port = 0xA
        elif i == 11 : self.the_port = 0xB
        elif i == 12 : self.the_port = 0xC
        elif i == 13 : self.the_port = 0xD
        elif i == 14 : self.the_port = 0xE
        elif i == 15 : self.the_port = 0xF
        else : self.the_port = -1

    def change_channel(self, i) :
        if i < 8 : self.the_channel = i
        else : self.the_channel = -1

    def change_direction(self, i) :
        self.the_direction = i

    def printText_out(self, pk):
        if self.the_direction > 0 : self.printText(pk, False)

    def printText_in(self, pk):
        if self.the_direction == 0 or self.the_direction > 1: self.printText(pk, True)

    def printText(self, pk, into):
        # Make sure we get printouts from the Crazyflie into the log (such as
        # build version and test ok/fail)
####        logger.info('port {}, channel {}'.format(self.the_port, self.the_channel))
        if (pk._get_port() == self.the_port or self.the_port < 0)\
                 and (pk._get_channel() == self.the_channel or self.the_channel < 0)\
                 and (self.line <= self.lines_max or self.lines_max < 0) :
####        if (pk._get_channel() == self.the_channel or self.the_channel < 0)\
####                 and (self.line <= self.lines_max or self.lines_max < -1) :
            self.receive.insertPlainText(str(self.line)+" - ")
            if into : self.receive.insertPlainText("IN"+" - ")
            else : self.receive.insertPlainText("OUT"+" - ")
            self.receive.insertPlainText(str(pk._get_port())+" - ")
            self.receive.insertPlainText(str(pk._get_channel())+" - ")
            self.receive.insertPlainText(str(pk._get_data())+"\n")
            self.line += 1

    def clear(self):
        self.receive.clear()

    def _connected(self, link_uri):
        """Callback when the Crazyflie has been connected"""
        self.startButton.setEnabled(True)
        self.startButton.clicked.connect(self.start)

    def _disconnected(self, link_uri):
        """Callback for when the Crazyflie has been disconnected"""
        self.startButton.setEnabled(False)
####        self.startButton.clicked.disconnect(self.start)

