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
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
"""
This tab plots different logging data defined by configurations that has been
pre-configured.
"""
import logging

import cfclient
import math
from PyQt5.QtCore import pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QGraphicsScene
from cfclient.ui.tab import Tab
from cflib.crazyflie.log import LogConfig
from PyQt5 import QtCore
from PyQt5 import QtGui
######from PyQt5.QtCore import QUrl
###### from PyQt5 import QtNetwork
######from PyQt5 import QtWebEngineCore
######from PyQt5 import QtWebEngineWidgets
######from PyQt5.QtWebEngineWidgets import QWebEnginePage
######rom PyQt5.QtWebEngineWidgets import QWebEngineView
######from PyQt5 import QtWebKit
from PyQt5 import uic

__author__ = 'Bitcraze AB'
__all__ = ['GpsTab']

logger = logging.getLogger(__name__)

gps_tab_class = uic.loadUiType(cfclient.module_path +
                               "/ui/tabs/gpsTab.ui")[0]


class GpsTab(Tab, gps_tab_class):
    """Tab for plotting logging data"""

    _log_data_signal = pyqtSignal(int, object, object)
    _log_error_signal = pyqtSignal(object, str)

    _disconnected_signal = pyqtSignal(str)
    _connected_signal = pyqtSignal(str)
####    _console_signal = pyqtSignal(str)
    _update = pyqtSignal(str)

    def __init__(self, tabWidget, helper, *args):
        super(GpsTab, self).__init__(*args)
        self.setupUi(self)

        self.tabName = "GPS"
        self.menuName = "GPS"

        self.tabWidget = tabWidget
        self.helper = helper
        self._cf = helper.cf

        self.scene = QGraphicsScene(0, 0, 600, 600, self.tabWidget)
        self.plan.setScene(self.scene)
        self.scene.addLine(300, 0, 300, 600)
        self.scene.addLine(0, 300, 600, 300)

        # Connect the signals
        self._log_data_signal.connect(self._log_data_received)
        self._log_error_signal.connect(self._logging_error)
        self._connected_signal.connect(self._connected)
        self._disconnected_signal.connect(self._disconnected)
        self.stop_messages.clicked.connect(self._stop_m)
        self.clear_messages.clicked.connect(self._clear_m)

        # Connect the callbacks from the Crazyflie API
        self.helper.cf.disconnected.add_callback(
            self._disconnected_signal.emit)
        self.helper.cf.connected.add_callback(
            self._connected_signal.emit)
        self._update.connect(self.printText)
        self.helper.cf.console.receivedChar.add_callback(self._update.emit)

        self.lat = 0
        self.longe = 0
        self.run = False
       

        """
###################################################################### Visualisation carte
        self.view = QtWebEngineWidgets.QWebEngineView(self.tabWidget)

######        cache = QtNetwork.QNetworkDiskCache()
######        cache.setCacheDirectory(cfclient.config_path + "/cache")
######        view.page().networkAccessManager().setCache(cache)
######        view.page().networkAccessManager()
######        self.page = self.view.

######        self.url = QUrl("file://"+cfclient.module_path + "/resources/map.html")

######        self.url = QUrl("file:///home/jclaude/mapbox_test.html")
        self.url = QUrl("http://www.jcmitteau.net")
######        self.view.
######        view.page().runJavaScript(cfclient.module_path + "/resources/BIDULE.html", self.script_error)
######        view.page().setLinkDelegationPolicy(QtWebKit.QWebPage.DelegateAllLinks)
######        view.load(QtCore.QUrl(cfclient.module_path + "/resources/map.html"))
######        view.linkClicked.connect(QtGui.QDesktopServices.openUrl)

        self.map_layout.addWidget(self.view)
        self.page = QWebEnginePage(self.view)
        self.view.setPage(self.page)
        self.view.load(self.url)
        self.page.loadFinished.connect(self.onLoadFinished)

######        self.onLoadFinished()
###################################################################### Visualisation carte
        
        self._reset_max_btn.clicked.connect(self._reset_max)


        self._max_speed = 0.0

    def script_error(self, s) :
        logger.info('erreur de script {}'.format(s))

    def onLoadFinished(self):
        with open(cfclient.module_path + "/resources/map.js", 'r') as f:
#####            frame = self.view.page().mainFrame()
            self.view.page().runJavaScript(f.read())

    @QtCore.pyqtSlot(float, float)
    def onMapMove(self, lat, lng):
        return

    def panMap(self, lng, lat):
        frame = self.view.page().mainFrame()
        frame.evaluateJavaScript('map.panTo(L.latLng({}, {}));'.format(lat,
                                                                       lng))

    def _place_cf(self, lng, lat, acc):
        frame = self.view.page().mainFrame()
        frame.evaluateJavaScript('cf.setLatLng([{}, {}]);'.format(lat, lng))
        """

    def _connected(self, link_uri):
        lg = LogConfig("GPS", 1000)
        lg.add_variable("gps.lat")
        lg.add_variable("gps.lon")
        lg.add_variable("gps.hAcc")
        lg.add_variable("gps.hMSL")
        lg.add_variable("gps.nsat")
        lg.add_variable("gps.fix")
        self._cf.log.add_config(lg)
        if lg.valid:
            lg.data_received_cb.add_callback(self._log_data_signal.emit)
            lg.error_cb.add_callback(self._log_error_signal.emit)
            lg.start()
        else:
            logger.warning("Could not setup logging block for GPS!")
####        self._max_speed = 0.0

    def _disconnected(self, link_uri):
        """Callback for when the Crazyflie has been disconnected"""
        return

    def printText(self, text):
        # Make sure we get printouts from the Crazyflie into the log (such as
        # build version and test ok/fail)
        if self.run and text[0] == "$" : self.messages.insertPlainText(text)

    def _stop_m(self):
        if self.run : self.run = False
        else : self.run = True

    def _clear_m(self):
        self.messages.clear()

    def _logging_error(self, log_conf, msg):
        """Callback from the log layer when an error occurs"""
        QMessageBox.about(self, "Plot error", "Error when starting log config"
                          " [%s]: %s" % (log_conf.name, msg))

    def _reset_max(self):
        """Callback from reset button"""
####        self._max_speed = 0.0
####        self._speed_max.setText(str(self._max_speed))
        self._long.setText("")
        self._lat.setText("")
        self._height.setText("")
####        self._speed.setText("")
####        self._heading.setText("")
####        self._accuracy.setText("")
        self._fix_type.setText("")

    def _log_data_received(self, timestamp, data, logconf):
        """Callback when the log layer receives new data"""
        longe = float(data["gps.lon"]) / 10000000.0
####        longe = 40.25478
        if longe > 0 : le = "E"
        elif longe < 0 :
            le = "W"
            longe = -longe
        else : le = ""
        ld = math.floor(longe)
        l1 = (longe-ld) * 60
        lm = math.floor(l1)
        ls = (l1-lm) * 60
        ls = math.floor(ls * 100000)/100000
        lat = float(data["gps.lat"]) / 10000000.0
####       lat = -28.2593
        if lat > 0 : te = "N"
        elif lat < 0 :
            te = "S"
            lat = -lat
        else : te = ""
        td = math.floor(lat)
        t1 = (lat-td) * 60
        tm = math.floor(t1)
        ts = (t1-tm) * 60
        ts = math.floor(ts * 100000)/100000
        ft = data["gps.fix"]
####        ht = 1005.4581
        ht = float(data["gps.hMSL"])

        if self._lat != lat or self._long != longe:
            self._long.setText("{}° {}' {:.3f}\" {}".format(ld,lm,ls,le))
            self._lat.setText("{}° {}' {:.3f}\" {}".format(td,tm,ts,te))
            self._nbr_locked_sats.setText(str(data["gps.nsat"]))
            self._height.setText("{:.2f} meter".format(ht))
####            self._place_cf(long, lat, 1)
            self._lat = lat
            self._long = longe
            self._fix_type.setText("{}".format(data["gps.fix"]))

