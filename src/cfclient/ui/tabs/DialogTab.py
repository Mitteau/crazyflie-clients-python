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
import struct


from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import *

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

####box_class = uic.loadUiType(cfclient.module_path +
####                                            '/ui/tabs/PortChannel.ui')

"""class Set_port_channel(QGroupBox, box_class):

    def __init__(self, tabWidget, helper, *args):
        super(Set_port_channel, self).__init__(*args)
        self.setupUi(self)
"""

class DialogTab(Tab, dialog_tab_class):
    """Dialog tab for dialog with Crazyflie"""
    _received_pk = pyqtSignal(object)
    _sent_pk = pyqtSignal(object)
    the_port_e = 0x3
    the_channel_e = 0
    p = 0
    c = 0

    def __init__(self, tabWidget, helper, *args):
        super(DialogTab, self).__init__(*args)
        self.setupUi(self)

        self.tabName = "Dialog"
        self.menuName = "Dialog"

        self.tabWidget = tabWidget
        self._helper = helper
        self.pk = CRTPPacket()

        self._received_pk.connect(self.printText_in)
        self._sent_pk.connect(self.printText_out)
        self._helper.cf.packet_received.add_callback(self._received_pk.emit)
        self._helper.cf.packet_sent.add_callback(self._sent_pk.emit)
        self.startButton.setText("Stop")
        self.startButton.clicked.connect(self.start)
        self.speakButton.clicked.connect(self.speak)
        self.send.returnPressed.connect(self.send_pk)
        self.line_number.activated.connect(self.change_lines)
        self.format.activated.connect(self.change_format)
        self.port.activated.connect(self.change_port)
        self.channel.activated.connect(self.change_channel)
        self.direction.activated.connect(self.change_direction)
        
        self.send.setEnabled(False)
        self.clearButton.clicked.connect(self.clear)
        self.started = True
        self.the_port = 0x0
        self.the_channel = -1
        self.line = 1
        self.lines_max = 10
        self.the_direction = 2
        self.speaking = False
        self.format = 0
        self.no_header = False

        self.Q = QWidget(self.tabWidget)
        self.Q.setVisible(False)
        self.Q.setGeometry(30,120,301,163)
        self.L_port_channel = QVBoxLayout()
        self.Q.setLayout(self.L_port_channel)
        self.label = QLabel()
        self.Q.setGeometry(30,120,301,163)
        label_title = QLabel("Select port and channel")
        self.L_port_channel.addWidget(label_title)
        self.Q_port = QComboBox()
        self.Q_port.currentIndexChanged.connect(
            lambda index: DialogTab.change_port_e(index))
        self.Q_port.addItem("Port 0x0 Console")
        self.Q_port.addItem("Port 0x1")
        self.Q_port.addItem("Port 0x2 Parameters")
        self.Q_port.addItem("Port 0x3 Commander")
        self.Q_port.addItem("Port 0x4 Memory")
        self.Q_port.addItem("Port 0x5 Log")
        self.Q_port.addItem("Port 0x6 Localization")
        self.Q_port.addItem("Port 0x7 Generic set points")
        self.Q_port.addItem("Port 0x8")
        self.Q_port.addItem("Port 0x9")
        self.Q_port.addItem("Port 0xA")
        self.Q_port.addItem("Port 0xB")
        self.Q_port.addItem("Port 0xC")
        self.Q_port.addItem("Port 0xD Platform")
        self.Q_port.addItem("Port 0xE Client-side debugging")
        self.Q_port.addItem("Port 0xF Link layer")
        self.Q_port.addItem("No header")
        self.L_port_channel.addWidget(self.Q_port)
        self.L_channel = QHBoxLayout()
        self.label = QLabel()
        self.label.setText("Channel: ")
        self.Q_channel = QComboBox()
        self.Q_channel.currentIndexChanged.connect(
            lambda index: DialogTab.change_channel_e(index))
        self.Q_channel.addItem("0")
        self.Q_channel.addItem("1")
        self.Q_channel.addItem("2")
        self.Q_channel.addItem("3")
        self.Q_channel.addItem("4")
        self.Q_channel.addItem("5")
        self.Q_channel.addItem("6")
        self.Q_channel.addItem("7")
        self.Q_channel.setCurrentIndex(self.the_channel_e)
        self.L_channel.addWidget(self.label)
        self.L_channel.addWidget(self.Q_channel)
        self.L_port_channel.addLayout(self.L_channel)
        self.H_buttons = QHBoxLayout()
        self.B_abort = QPushButton("Abort")
        self.B_abort.clicked.connect(
            lambda index: DialogTab.close_abort(self.Q))
        self.B_accept = QPushButton("Accept")
        self.B_accept.clicked.connect(
            lambda index: DialogTab.close_accept(self.Q))
        self.H_buttons.addWidget(self.B_abort)
        self.H_buttons.addWidget(self.B_accept)
        self.L_port_channel.addLayout(self.H_buttons)


    def quality(self) :
        pass

    def error(self) :
        pass

    def start(self) :
        self.line = 1
        if self.started : 
            self.lines_max = -1
            self.started = False
            self.startButton.setText("Hear")
        else :
            self.startButton.setText("Stop")
            self.started = True
            i = self.line_number.currentIndex()
            self.change_lines(i)

    def change_lines(self, i) :
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
        elif i == 16 : self.the_port = 0xFF
        elif i == 17 : self.the_port = 0xFE

    def change_channel(self, i) :
        if i < 8 : self.the_channel = i
        else : self.the_channel = -1

    def change_direction(self, i) :
        self.the_direction = i

    def change_format(self, i) :
        self.format = i

    def printText_out(self, pk):
        if self.the_direction > 0 : 
            self.printText(pk, False)

    def printText_in(self, pk):
        if self.the_direction == 0 or self.the_direction > 1: 
            self.printText(pk, True)

    def printText(self, pk, into):
        oui = False
        if (self.line > self.lines_max) and (self.lines_max >= 0) : 
            self.startButton.setText("Hear")
            self.started = False
        if pk.header == 0xFF and self.the_port == 0xFF : oui = True
        elif pk._get_port() == self.the_port : oui = True
        else : oui = False

        if (oui or self.the_port  == 0xFE)\
                 and (pk._get_channel() == self.the_channel or self.the_channel < 0)\
                 and (self.line <= self.lines_max or self.lines_max < 0)\
                 and self.started :
            if into : self.receive.setTextColor(Qt.black)
            else : self.receive.setTextColor(Qt.red)
            self.receive.insertPlainText(str(self.line)+" - ")
            if into : self.receive.insertPlainText("IN"+" - ")
            else : self.receive.insertPlainText("OUT"+" - ")
            if pk.header == 0xFF : self.receive.insertPlainText("0xFF"+" - ")
            else :
                self.receive.insertPlainText(str(pk._get_port())+" - ")
                self.receive.insertPlainText(str(pk._get_channel())+" - ")
            if self.format == 1 :
                self.receive.insertPlainText(str(pk._get_data())+"\n")
            else :
                b = pk._get_data()
                s = b.hex()
                self.receive.insertPlainText("   "+s+"\n")
            self.line += 1
            maxi = self.receive.verticalScrollBar().maximum()
            self.receive.verticalScrollBar().setValue(maxi)

    def clear(self):
        self.receive.clear()

    def set_port_channel(self):
        self.Q_port.setCurrentIndex(self.the_port_e)
        self.Q_channel.setCurrentIndex(self.the_channel_e)
        self.Q.show()

        

    def speak(self) :
        if self.speaking :
            self.send.setEnabled(False)
            self.speaking = False
        else :
            self.send.setEnabled(True)
            self.set_port_channel()
            self.speaking = True
            self.send.setFocus()

    def send_pk(self) :
            t = self.send.text()
            b = bytearray()
            b = b.fromhex(t)
            self.echo.append(t)
            self.send.setText("")
            if DialogTab.the_port_e != 0xFF :
                self.pk.set_header(DialogTab.the_port_e, DialogTab.the_channel_e)
            else :
                self.pk.header = 0xFF
            self.pk._set_data(b)
            self._helper.cf.send_packet(self.pk)


    @pyqtSlot(int)
    @pyqtSlot(int, int, int)


    def change_port_e(i) :
        if i == 0 : DialogTab.p =0x0
        elif i == 1 : DialogTab.p = 0x1
        elif i == 2 : DialogTab.p = 0x2
        elif i == 3 : DialogTab.p = 0x3
        elif i == 4 : DialogTab.p = 0x4
        elif i == 5 : DialogTab.p = 0x5
        elif i == 6 : DialogTab.p = 0x6
        elif i == 7 : DialogTab.p = 0x7
        elif i == 8 : DialogTab.p = 0x8
        elif i == 9 : DialogTab.p = 0x9
        elif i == 10 : DialogTab.p = 0xA
        elif i == 11 : DialogTab.p = 0xB
        elif i == 12 : DialogTab.p = 0xC
        elif i == 13 : DialogTab.p = 0xD
        elif i == 14 : DialogTab.p = 0xE
        elif i == 15 : DialogTab.p = 0xF
        elif i == 16 : DialogTab.p = 0xFF

    def change_channel_e(i) :
        if i < 8 : DialogTab.c = i

    def close_accept(Q) :
        DialogTab.the_port_e = DialogTab.p
        DialogTab.the_channel_e = DialogTab.c
        Q.close()

    def close_abort(Q) :
        Q.close()


