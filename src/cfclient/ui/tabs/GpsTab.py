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
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QTime
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QGraphicsScene

from PyQt5.QtGui import QPixmap
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

    _log_data_signal_b = pyqtSignal(int, object, object)
    _log_data_signal_t = pyqtSignal(int, object, object)
    _log_error_signal = pyqtSignal(object, str)
######
    _disconnected_signal = pyqtSignal(str)
    _connected_signal = pyqtSignal(str)
    _console_signal = pyqtSignal(str)
    _update = pyqtSignal(str)
    _buffer_full = pyqtSignal(str)

    def __init__(self, tabWidget, helper, *args):
        super(GpsTab, self).__init__(*args)
        self.setupUi(self)

        self.tabName = "GPS"
        self.menuName = "GPS"

        self.tabWidget = tabWidget
        self.helper = helper
        self._cf = helper.cf

        self.scene = QGraphicsScene(0, 0, 1200, 1200, self.tabWidget) #### unités cm
        self.plan.setScene(self.scene)
        self.background = QPixmap()
        self.background.load("/home/jclaude/BTCZ/fond.png")
        self.scene.addPixmap(self.background)
        self.center_x = -60 #### coordonnées du point d'envol ?
        self.center_y = 350
        self.scene.addLine(600+self.center_x, 0, 600+self.center_x, 1200)
        self.scene.addLine(0, 600+self.center_y, 1200, 600+self.center_y)
        self.scene.addEllipse(550+self.center_x, 550+self.center_y, 100, 100)
        self.scene.addEllipse(500+self.center_x, 500+self.center_y, 200, 200)
        self.scene.addEllipse(350+self.center_x, 350+self.center_y, 500, 500)
        self.scene.addEllipse(100+self.center_x, 100+self.center_y, 1000, 1000)
        self.plan.translate(self.center_x, self.center_y)

        # Connect the signals
        self._log_data_signal_b.connect(self._log_data_received_b)
        self._log_data_signal_t.connect(self._log_data_received_t)
        self._log_error_signal.connect(self._logging_error)
        self._connected_signal.connect(self._connected)
        self._disconnected_signal.connect(self._disconnected)
        self.stop_messages.clicked.connect(self._stop_m)
        self.clear_messages.clicked.connect(self._clear_m)
        self._ok_messages.clicked.connect(self._ok_m)

        # Connect the callbacks from the Crazyflie API
        self.helper.cf.disconnected.add_callback(
            self._disconnected_signal.emit)
        self.helper.cf.connected.add_callback(
            self._connected_signal.emit)
        self._update.connect(self.print_info)
        self._buffer_full.connect(self.print_info)
        self.helper.cf.console.receivedChar.add_callback(self._update.emit)

        self.lat_d = 0
        self.lat_m = 0
        self.longe_d = 0
        self.longe_m = 0
        self.run = False
        self.buff = []
        self.show_m = False
        self.t_gps = QTime()

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
        lg = LogConfig("GPS_base", 1000)
        lg.add_variable("gps_base.time")
        lg.add_variable("gps_base.hAcc")
        lg.add_variable("gps_base.nsat")
        lg.add_variable("gps_base.fixquality")
        self._cf.log.add_config(lg)
        if lg.valid:
            lg.data_received_cb.add_callback(self._log_data_signal_b.emit)
            lg.error_cb.add_callback(self._log_error_signal.emit)
            lg.start()
            logger.info('Gpsbase connecté')
        else:
            logger.warning("Could not setup logging block for GPS_base!")
####        self._max_speed = 0.0
        lg1 = LogConfig("GPS_tracking", 1000)
        lg1.add_variable("gps_track.lat_d")
        lg1.add_variable("gps_track.lat_m")
        lg1.add_variable("gps_track.NS")
        lg1.add_variable("gps_track.lon_d")
        lg1.add_variable("gps_track.lon_m")
        lg1.add_variable("gps_track.EW")
        lg1.add_variable("gps_track.hMSL")
        self._cf.log.add_config(lg1)
        if lg1.valid:
            lg1.data_received_cb.add_callback(self._log_data_signal_t.emit)
            lg1.error_cb.add_callback(self._log_error_signal.emit)
            lg1.start()
            logger.info('Gpstrack connecté')
        else:
            logger.warning("Could not setup logging block for GPS_tracking!")
####        self._max_speed = 0.0
        self.helper.cf.param.set_value("gps.messages", "0")
        self.show_m = False
        self.run = True
        self.messages.clear()
        self._ok_messages.setChecked(self.show_m)
        
######################################################################
        """
        """
    def _ok_m(self, value) :
        self.show_m = value
        self.helper.cf.param.set_value("gps.messages", str(value))
        self.helper.cf.param.set_value("pm.timeOutSystem", str(1-value))
        self.run = self.show_m

    def _disconnected(self, link_uri):
        """Callback for when the Crazyflie has been disconnected"""
        return

####    def printText(self, text):
####        # Make sure we get printouts from the Crazyflie into the log (such as
        # build version and test ok/fail)
####        if self.run : self.messages.insertPlainText(text) #### Cas NMEA seulement

    def bufferize(self, ch) :
        pass
####        logger.info("{}".format(ch))
####        if ch[0] == "$" :
 ####           self.init_message = True
####            logger.info('XXXXXXXXXXXXXXXXXXXXXXXXXself.init vrai')
####        if (ord(ch[0]) == 13) : #### and self.init_message :
####            self.init_message = False
####            logger.info('YYYYYYYYYYYYYYYYYYYYYYYYYself.init faux')
####            self.messages.insertPlainText(self.buff[0])
####            self._buffer_full.emit(self.buff[0])
####            self.messages.insertPlainText('\n')
####            self.buff[0] = 0
 ####       if self.init_message :
####            self.buff.append(ch[0])
####        self.messages.insertPlainText(ch)
####            logger.info("{}".format(hex(ord(ch[0]))))


    def print_info(self, text) :
        if self.run and self.show_m :
            self.messages.insertPlainText(text) #### Cas NMEA seulement
            maxi = self.messages.verticalScrollBar().maximum()
            self.messages.verticalScrollBar().setValue(maxi)

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

    def _log_data_received_b(self, timestamp, data, logconf):
        """Callback when the log layer receives new data"""
        ns = data["gps_base.nsat"]
####        logger.info("n sat {}".format(ns))
        self._nbr_locked_sats.setText("%d" % ns)
        self._fix_type.setText("%d" % data["gps_base.fixquality"])
        tm = data["gps_base.time"]
####        logger.info("gps time {}".format(tm))
        ts = int(tm)
        th = ts // 3600
        th = th % 24
        ti = ts % 3600
        tmn = ti // 60
        tsec = ti % 60
        tmsec = int((tm - ts) *100)
####        logger.info("time formaté {} h {} m {},{} sec".format(th, tmn, tsec, tmsec))
        self.t_gps.setHMS(th, tmn, tsec, tmsec)
        self._time.setTime(self.t_gps)
        self._hdop.setText("%0.2f" % data["gps_base.hAcc"])
####        self._fix_type.setText("{}".format(data["gps_base.fix"]))

    def _log_data_received_t(self, timestamp, data, logconf):
        """Callback when the log layer receives new data"""
        le = data["gps_track.EW"]
        longe_d = data["gps_track.lon_d"]
####        logger.info('Longitude  d° uint32 >{}<'.format(longe_d))
        longe_m = data["gps_track.lon_m"]
####        logger.info('Longitude  m\' uint32 >{}<'.format(longe_m))
        ld = longe_d
        if longe_m != 0 : lm = longe_m // 10000000 #### cas égal 0 ?
        else : lm = 0
####        logger.info('Longitude  m\' uint32 >{}<'.format(lm))
        l1 = lm * 10000000
        ls = (longe_m - l1) * 6.
        if ls != 0 : ls = ls / 100000
####        logger.info('Longitude  s" uint32 >{}<'.format(ls))

        te = data["gps_track.NS"]
        lat_d = data["gps_track.lat_d"]
        lat_m = data["gps_track.lat_m"]
        td = lat_d
        if lat_m != 0 : tm = lat_m // 10000000
        else : tm = 0
        t1 = tm * 10000000
        ts = (lat_m - t1) * 6.
        if ts != 0 : ts = ts / 100000
        ht = float(data["gps_track.hMSL"])

        if self.lat_d != lat_d or self.longe_d != longe_d\
             or self.lat_m != lat_m or self.longe_m != longe_m :
            self._long.setText("%d° %d' %f\" %c" % (ld,lm,ls,le))
            self._lat.setText("%d° %d' %f\" %c" % (td,tm,ts,te))
            self._height.setText("%.1f" % ht)
            self.lat_m = lat_m
            self.lat_d = lat_d
            self.longe_m = longe_m
            self.longe_d = longe_d
