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
The flight control tab shows telemetry data and flight settings.
"""

import logging

from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import QMessageBox

import cfclient
from cfclient.ui.widgets.ai import AttitudeIndicator

from cfclient.utils.config import Config
from cflib.crazyflie.log import LogConfig

from cfclient.utils.input import JoystickReader

from cfclient.ui.tab import Tab

LOG_NAME_ESTIMATED_Z = "stateEstimate.z"
LOG_NAME_ZRANGE = "range.zrange"
LOG_NAME_ALT = "baro.asl"
TARGET_HEIGHT = .45

__author__ = 'Bitcraze AB'
__all__ = ['FlightTab']

logger = logging.getLogger(__name__)

flight_tab_class = uic.loadUiType(cfclient.module_path +
                                  "/ui/tabs/flightTab.ui")[0]

MAX_THRUST = 65536.0

class FlightTab(Tab, flight_tab_class):
    uiSetupReadySignal = pyqtSignal()

    _motor_data_signal = pyqtSignal(int, object, object)
    _imu_data_signal = pyqtSignal(int, object, object)
    _baro_data_signal = pyqtSignal(int, object, object)
    _zrange_data_signal = pyqtSignal(int, object, object)

    _input_updated_signal = pyqtSignal(float, float, float, float)
    _rp_trim_updated_signal = pyqtSignal(float, float)
    _emergency_stop_updated_signal = pyqtSignal(bool)
    _assisted_control_updated_signal = pyqtSignal(bool)
    _poshold_input_updated_signal = pyqtSignal(float)   ####
    _althold_input_updated_signal = pyqtSignal(float, float, float, float)
    _heighthold_input_updated_signal = pyqtSignal(float, float, float, float)
    _hover_input_updated_signal = pyqtSignal(float, float, float, float)

    _log_error_signal = pyqtSignal(object, str)

    # UI_DATA_UPDATE_FPS = 10

    connectionFinishedSignal = pyqtSignal(str)
    disconnectedSignal = pyqtSignal(str)

    _limiting_updated = pyqtSignal(bool, bool, bool)
    _all_sound = False
    _bascule = False

    def __init__(self, tabWidget, helper, *args):
        super(FlightTab, self).__init__(*args)
        self.setupUi(self)

        self.tabName = "Flight Control"
        self.menuName = "Flight Control"

        self.tabWidget = tabWidget
        self.helper = helper

        self.disconnectedSignal.connect(self.disconnected)
        self.connectionFinishedSignal.connect(self.connected)
        # Incomming signals
        self.helper.cf.connected.add_callback(
            self.connectionFinishedSignal.emit)
        self.helper.cf.disconnected.add_callback(self.disconnectedSignal.emit)

        self._input_updated_signal.connect(self.updateInputControl)
        self.helper.inputDeviceReader.input_updated.add_callback(
            self._input_updated_signal.emit)
        self._rp_trim_updated_signal.connect(self.calUpdateFromInput)
        self.helper.inputDeviceReader.rp_trim_updated.add_callback(
            self._rp_trim_updated_signal.emit)
        self._emergency_stop_updated_signal.connect(self.updateEmergencyStop)
        self.helper.inputDeviceReader.emergency_stop_updated.add_callback(
            self._emergency_stop_updated_signal.emit)

        self.helper.inputDeviceReader.althold_input_updated.add_callback(
            self._althold_input_updated_signal.emit)
        self._althold_input_updated_signal.connect(
            self._althold_input_updated)
        self.helper.inputDeviceReader.heighthold_input_updated.add_callback(
            self._heighthold_input_updated_signal.emit)
        self._heighthold_input_updated_signal.connect(
            self._heighthold_input_updated)
        self.helper.inputDeviceReader.hover_input_updated.add_callback(
            self._hover_input_updated_signal.emit)
        self._hover_input_updated_signal.connect(
            self._hover_input_updated)
        self.helper.inputDeviceReader.assisted_control_updated.add_callback(
            self._assisted_control_updated_signal.emit)
        self._assisted_control_updated_signal.connect(
            self._basculeur)

        self._imu_data_signal.connect(self._imu_data_received)
        self._baro_data_signal.connect(self._baro_data_received)
        self._motor_data_signal.connect(self._motor_data_received)
        self._zrange_data_signal.connect(self._height_data_received)

        self._log_error_signal.connect(self._logging_error)

        # Connect UI signals that are in this tab
        self.flightModeCombo.currentIndexChanged.connect(self.flightmodeChange)
        self.minThrust.valueChanged.connect(self.minMaxThrustChanged)
        self.maxThrust.valueChanged.connect(self.minMaxThrustChanged)
        self.thrustLoweringSlewRateLimit.valueChanged.connect(
            self.thrustLoweringSlewRateLimitChanged)
        self.slewEnableLimit.valueChanged.connect(
            self.thrustLoweringSlewRateLimitChanged)
        self.targetCalRoll.valueChanged.connect(self._trim_roll_changed)
        self.targetCalPitch.valueChanged.connect(self._trim_pitch_changed)
        self.maxAngle.valueChanged.connect(self.maxAngleChanged)
        self.maxYawRate.valueChanged.connect(self.maxYawRateChanged)
        self.uiSetupReadySignal.connect(self.uiSetupReady)
        self.clientXModeCheckbox.toggled.connect(self.changeXmode)
        self.isInCrazyFlightmode = False
        self.uiSetupReady()
        self.checkAssisted.setEnabled(False) ####
        self.checkAssisted.clicked.connect(self.set_cf_assist)
        self.emergency.clicked.connect(self.releaseEmergencyStop)

        self.clientXModeCheckbox.setChecked(Config().get("client_side_xmode"))

        self.crazyflieXModeCheckbox.clicked.connect(
            lambda enabled:
            self.helper.cf.param.set_value("flightmode.x",
                                           str(enabled)))

        self.angularPidRadioButton.clicked.connect(
            lambda enabled:
            self.helper.cf.param.set_value("flightmode.ratepid",
                                           str(not enabled)))

        self.ratePidRadioButton.clicked.connect(
            lambda enabled:
            self.helper.cf.param.set_value("flightmode.ratepid",
                                           str(enabled)))


        self._led_ring_headlight.clicked.connect(
            lambda enabled:
            self.helper.cf.param.set_value("ring.headlightEnable",
                                           str(enabled)))

        self._sound_all.clicked.connect(
            lambda enabled: self.set_all_sound(enabled))


        self.helper.cf.param.add_update_callback(
            group="flightmode", name="xmode",
            cb=(lambda name, checked:
                self.crazyflieXModeCheckbox.setChecked(eval(checked))))

        self.helper.cf.param.add_update_callback(
            group="flightmode", name="ratepid",
            cb=(lambda name, checked:
                self.ratePidRadioButton.setChecked(eval(checked))))

        self.helper.cf.param.add_update_callback(
            group="ring", name="headlightEnable",
            cb=(lambda name, checked:
                self._led_ring_headlight.setChecked(eval(checked))))

        self.helper.cf.param.add_update_callback(
            group="flightmode", name="althold",
            cb=self._ok_assisted)

        self.helper.cf.param.add_update_callback(
            group="cpu", name="flash",
            cb=self._set_enable_client_xmode)

        self.helper.cf.param.add_update_callback(
            group="ring",
            name="effect",
            cb=self._ring_effect_updated)

        self.helper.cf.param.add_update_callback(
            group="imu_sensors",
            cb=self._set_available_sensors)

        self._ledring_nbr_effects = 0
        self._sound_nbr_effects = 0

        self.logBaro = None
        self.logAltHold = None

        self.ai = AttitudeIndicator()
        self.verticalLayout_4.addWidget(self.ai)
        self.splitter.setSizes([1000, 1])

        self.targetCalPitch.setValue(Config().get("trim_pitch"))
        self.targetCalRoll.setValue(Config().get("trim_roll"))

        self.height = 0.
        self._tf_state = 0
        self._ring_effect = 0
        self._soundeffect = 0
        self.concted = False
        self.assisted = False
        self.is_height = False
        self.estimated_z = 0.
        self.mode_assist = 0
        self.emergency.setVisible(False)
        self.label_18.setVisible(False)
        self.label_19.setVisible(False)
        self.repet = 0

####        self.widgetE.setEnabled(False)

        # Connect callbacks for input device limiting of rpöö/pitch/yaw/thust
        self.helper.inputDeviceReader.limiting_updated.add_callback(
            self._limiting_updated.emit)
        self._limiting_updated.connect(self._set_limiting_enabled)

    def _set_enable_client_xmode(self, name, value):
        if eval(value) <= 128:
            self.clientXModeCheckbox.setEnabled(True)
        else:
            self.clientXModeCheckbox.setEnabled(False)
            self.clientXModeCheckbox.setChecked(False)

        self.helper.cf.param.all_updated.add_callback(
            self._sound_populate_dropdown)

        self.helper.cf.param.all_updated.add_callback(
            self._ring_populate_dropdown)

    def set_all_sound(self, value):
        self._all_sound = value
        self.helper.cf.param.set_value("sound.effect", str(0))
        self._soundeffect = 0
        if value :
            self._sound_effect.setEnabled(True)
        else :
            self._sound_effect.setEnabled(False)

    def _set_limiting_enabled(self, rp_limiting_enabled,
                              yaw_limiting_enabled,
                              thrust_limiting_enabled):
        self.maxAngle.setEnabled(rp_limiting_enabled)
        self.targetCalRoll.setEnabled(rp_limiting_enabled)
        self.targetCalPitch.setEnabled(rp_limiting_enabled)
        self.maxYawRate.setEnabled(yaw_limiting_enabled)
        self.maxThrust.setEnabled(thrust_limiting_enabled)
        self.minThrust.setEnabled(thrust_limiting_enabled)
        self.slewEnableLimit.setEnabled(thrust_limiting_enabled)
        self.thrustLoweringSlewRateLimit.setEnabled(thrust_limiting_enabled)

    def thrustToPercentage(self, thrust):
        return ((thrust / MAX_THRUST) * 100.0)

    def uiSetupReady(self):
        flightComboIndex = self.flightModeCombo.findText(
            Config().get("flightmode"), Qt.MatchFixedString)
        if (flightComboIndex < 0):
            self.flightModeCombo.setCurrentIndex(0)
            self.flightModeCombo.currentIndexChanged.emit(0)
        else:
            self.flightModeCombo.setCurrentIndex(flightComboIndex)
            self.flightModeCombo.currentIndexChanged.emit(flightComboIndex)

    def _logging_error(self, log_conf, msg):
        QMessageBox.about(self, "Log error",
                          "Error when starting log config [%s]: %s" % (
                              log_conf.name, msg))

    def _motor_data_received(self, timestamp, data, logconf):
        if self.isVisible():
            self.actualM1.setValue(data["motor.m1"])
            self.actualM2.setValue(data["motor.m2"])
            self.actualM3.setValue(data["motor.m3"])
            self.actualM4.setValue(data["motor.m4"])

    def _baro_data_received(self, timestamp, data, logconf):
        if self.isVisible():
            if not self.is_height :
                estimated_z = data[LOG_NAME_ALT]
                self.estimated_z = estimated_z
                self.actualHeight.setText(("ASL = %.1f meter" % estimated_z))
                self.ai.setBaro(estimated_z, self.is_visible())

    def _height_data_received(self, timestamp, data, logconf):
        if self.isVisible():
            if self.is_height :
                estimated_z = data[LOG_NAME_ZRANGE]/1000.
                if estimated_z > 2. : self.actualHeight.setText(("Zranger error!"))
                else :
                    self.actualHeight.setText(("Height = %.2f meter" % estimated_z))
                    self.ai.setBaro(estimated_z, self.is_visible())

    def _althold_input_updated(self, roll, pitch, yaw, height):
        if (self.isVisible() and
              (self.helper.inputDeviceReader.get_assisted_control() ==
                 self.helper.inputDeviceReader.ASSISTED_CONTROL_ALTHOLD )):
####            self.ai.setHover(height+self.estimated_z, True)
            self.targetRoll.setText(("%0.0f deg" % roll))
            self.targetPitch.setText(("%0.0f deg" % pitch))
            self.targetYaw.setText(("%0.0f deg/s" % yaw))
            self.targetHeight.setText(("%0.2f meter" % (height)))
            self.height = height

    def _heighthold_input_updated(self, roll, pitch, yaw, height):
        if (self.isVisible() and
             (self.helper.inputDeviceReader.get_assisted_control() ==\
                 self.helper.inputDeviceReader.ASSISTED_CONTROL_HEIGHTHOLD)) :
            self.targetRoll.setText(("%0.0f deg" % roll))
            self.targetPitch.setText(("%0.0f deg" % pitch))
            self.targetYaw.setText(("%0.0f deg/s" % yaw))
            self.targetHeight.setEnabled(True)
            self.targetHeight.setText(("%0.2f meter" % height))
            self.height = height
####            self.ai.setHover(height, True)

    def _hover_input_updated(self, vx, vy, yaw, height):
        if (self.isVisible() and
                (self.helper.inputDeviceReader.get_assisted_control() ==
                 self.helper.inputDeviceReader.ASSISTED_CONTROL_HOVER)):
            self.targetRoll.setText(("%0.2f m/s" % vy))
            self.targetPitch.setText(("%0.2f m/s" % vx))
            self.targetYaw.setText(("%0.0f deg/s" % yaw))
            self.targetHeight.setText(("%0.2f meter" % height))
            self.height = height
####            self.ai.setHover(height, self.is_visible())

    def _imu_data_received(self, timestamp, data, logconf):
        if self.isVisible():
            self.actualRoll.setText(("%.1f deg" % data["stabilizer.roll"]))
            self.actualPitch.setText(("%.1f deg" % data["stabilizer.pitch"]))
            self.actualYaw.setText(("%.1f deg" % data["stabilizer.yaw"]))
            self.actualThrust.setText("%.0f %%" %
                                      self.thrustToPercentage(
                                          data["stabilizer.thrust"]))

            self.ai.setRollPitch(-data["stabilizer.roll"],
                                 data["stabilizer.pitch"], self.is_visible())

    def connected(self, linkURI):
        # IMU & THRUST
        lg = LogConfig("Stabilizer", Config().get("ui_update_period"))
        lg.add_variable("stabilizer.roll", "float")
        lg.add_variable("stabilizer.pitch", "float")
        lg.add_variable("stabilizer.yaw", "float")
        lg.add_variable("stabilizer.thrust", "uint16_t")

        try:
            self.helper.cf.log.add_config(lg)
            lg.data_received_cb.add_callback(self._imu_data_signal.emit)
            lg.error_cb.add_callback(self._log_error_signal.emit)
            lg.start()
        except KeyError as e:
            logger.warning(str(e))
        except AttributeError as e:
            logger.warning(str(e))

        # MOTOR
        lg = LogConfig("Motors", Config().get("ui_update_period"))
        lg.add_variable("motor.m1")
        lg.add_variable("motor.m2")
        lg.add_variable("motor.m3")
        lg.add_variable("motor.m4")

        try:
            self.helper.cf.log.add_config(lg)
            lg.data_received_cb.add_callback(self._motor_data_signal.emit)
            lg.error_cb.add_callback(self._log_error_signal.emit)
            lg.start()
        except KeyError as e:
            logger.warning(str(e))
        except AttributeError as e:
            logger.warning(str(e))

        self._assist_mode_combo.setEnabled(True)
        Config().set("assistedControl", 2)
        self.checkAssisted.setEnabled(True) ####
        self.targetHeight.setEnabled(True)
        self.targetHeight.setText("Not Set")
        self._populate_assisted_mode_dropdown()
        if self.helper.cf.mem.ow_search(vid=0xBC, pid=0x09) or \
                    self.helper.cf.mem.ow_search(vid=0xBC, pid=0x0A):    #### rajouter LPS ou GPS ?
            self.is_height = True
            lg = LogConfig("Range", Config().get("ui_update_period"))
            lg.add_variable("range.zrange") #### ne pas oubliier le cas hover
            try:
                self.helper.cf.log.add_config(lg)
                lg.data_received_cb.add_callback(self._zrange_data_signal.emit)
                lg.error_cb.add_callback(self._log_error_signal.emit)
                lg.start()
            except KeyError as e:
                logger.warning(str(e))
            except AttributeError as e:
                logger.warning(str(e))
        self.concted = True

    def _set_available_sensors(self, name, available):
        logger.info("[%s]: %s", name, available)
        available = eval(available)

        self.actualHeight.setEnabled(True)
        self.helper.inputDeviceReader.set_alt_hold_available(available)
        if not self.logBaro:
            # The sensor is available, set up the logging
            self.logBaro = LogConfig("Baro", 200)
            self.logBaro.add_variable(LOG_NAME_ALT, "float")

            try:
                self.helper.cf.log.add_config(self.logBaro)
                self.logBaro.data_received_cb.add_callback(
                    self._baro_data_signal.emit)
                self.logBaro.error_cb.add_callback(
                    self._log_error_signal.emit)
                self.logBaro.start()
            except KeyError as e:
                logger.warning(str(e))
            except AttributeError as e:
                logger.warning(str(e))

    def disconnected(self, linkURI):
        self.concted = False
        self.helper.inputDeviceReader.disconnected()
        self.ai.setRollPitch(0, 0)
        self.actualM1.setValue(0)
        self.actualM2.setValue(0)
        self.actualM3.setValue(0)
        self.actualM4.setValue(0)
        self.actualRoll.setText("")
        self.actualPitch.setText("")
        self.actualYaw.setText("")
        self.actualThrust.setText("")
        self.actualHeight.clear()
        self.targetHeight.setText("")
####        self.ai.setHover(0, self.is_visible())
        self.actualHeight.setEnabled(False)
        self.clientXModeCheckbox.setEnabled(False)
        self.logBaro = None
        self.logAltHold = None
        self._assist_mode_combo.clear()
        self._assist_mode_combo.setEnabled(False)
        self.is_height = False
        self._led_ring_effect.setEnabled(False)
        self._sound_effect.clear()

        self._led_ring_headlight.setChecked(False)
        self._led_ring_headlight.setEnabled(False)

        self._sound_effect.setEnabled(False)
        self._sound_effect.clear()

        self._all_sound = False
        self._sound_all.setChecked(False)
        self._sound_all.setEnabled(False)

        try:
            self._sound_effect.currentIndexChanged.disconnect(
                self._sound_effect_changed)
        except TypeError:
            # Signal was not connected
            pass
        try:
            self._led_ring_effect.currentIndexChanged.disconnect(
                self._ring_effect_changed)
        except TypeError:
            # Signal was not connected
            pass
        self._led_ring_effect.setCurrentIndex(-1)
        self._led_ring_headlight.setEnabled(False)

        try:
            self._assist_mode_combo.currentIndexChanged.disconnect(
                self._assist_mode_changed)
        except TypeError:
            # Signal was not connected
            pass

    def minMaxThrustChanged(self):
        self.helper.inputDeviceReader.min_thrust = self.minThrust.value()
        self.helper.inputDeviceReader.max_thrust = self.maxThrust.value()
        if (self.isInCrazyFlightmode is True):
            Config().set("min_thrust", self.minThrust.value())
            Config().set("max_thrust", self.maxThrust.value())

    def thrustLoweringSlewRateLimitChanged(self):
        self.helper.inputDeviceReader.thrust_slew_rate = (
            self.thrustLoweringSlewRateLimit.value())
        self.helper.inputDeviceReader.thrust_slew_limit = (
            self.slewEnableLimit.value())
        if (self.isInCrazyFlightmode is True):
            Config().set("slew_limit", self.slewEnableLimit.value())
            Config().set("slew_rate", self.thrustLoweringSlewRateLimit.value())

    def maxYawRateChanged(self):
        logger.debug("MaxYawrate changed to %d", self.maxYawRate.value())
        self.helper.inputDeviceReader.max_yaw_rate = self.maxYawRate.value()
        if (self.isInCrazyFlightmode is True):
            Config().set("max_yaw", self.maxYawRate.value())

    def maxAngleChanged(self):
        logger.debug("MaxAngle changed to %d", self.maxAngle.value())
        self.helper.inputDeviceReader.max_rp_angle = self.maxAngle.value()
        if (self.isInCrazyFlightmode is True):
            Config().set("max_rp", self.maxAngle.value())

    def _trim_pitch_changed(self, value):
        logger.debug("Pitch trim updated to [%f]" % value)
        self.helper.inputDeviceReader.trim_pitch = value
        Config().set("trim_pitch", value)

    def _trim_roll_changed(self, value):
        logger.debug("Roll trim updated to [%f]" % value)
        self.helper.inputDeviceReader.trim_roll = value
        Config().set("trim_roll", value)

    def calUpdateFromInput(self, rollCal, pitchCal):
        logger.debug("Trim changed on joystick: roll=%.2f, pitch=%.2f",
                     rollCal, pitchCal)
        self.targetCalRoll.setValue(rollCal)
        self.targetCalPitch.setValue(pitchCal)

    def updateInputControl(self, roll, pitch, yaw, thrust):
        self.targetRoll.setText(("%0.0f deg" % roll))
        self.targetPitch.setText(("%0.0f deg" % pitch))
        self.targetYaw.setText(("%0.0f deg/s" % yaw))
        self.targetThrust.setText(("%0.0f %%" %
                                   self.thrustToPercentage(thrust)))
        self.thrustProgress.setValue(thrust)

    def setMotorLabelsEnabled(self, enabled):
        self.M1label.setEnabled(enabled)
        self.M2label.setEnabled(enabled)
        self.M3label.setEnabled(enabled)
        self.M4label.setEnabled(enabled)

    def emergencyStopStringWithText(self, text):
        return ("<html><head/><body><p>"
                "<span style='font-weight:600; color:#7b0005;'>{}</span>"
                "</p></body></html>".format(text))

    def updateEmergencyStop(self, emergencyStop) :
        if self.concted :
            if emergencyStop :
                logger.info('Arrêt d\'urgence')
                self.set_cf_assist(False)
                self.emergency.setVisible(True)
                self.label_18.setVisible(True)
                self.label_19.setVisible(True)

    def releaseEmergencyStop(self) :
        self.repet +=1 
        if self.repet > 1 :
            self.emergency.setVisible(False)
            self.label_18.setVisible(False)
            self.label_19.setVisible(False)
            self.helper.inputDeviceReader.max_thrust = self.maxThrust.value()
            self.repet = 0


####            self.setMotorLabelsEnabled(False)
####            self.emergency_stop_label.setText(
####                self.emergencyStopStringWithText("Kill switch active"))
####        else:
####            self.setMotorLabelsEnabled(True)
####            self.emergency_stop_label.setText("")

    def flightmodeChange(self, item):
        Config().set("flightmode", str(self.flightModeCombo.itemText(item)))
        logger.debug("Changed flightmode to %s",
                     self.flightModeCombo.itemText(item))
        self.isInCrazyFlightmode = False
        if (item == 0):  # Normal
            self.maxAngle.setValue(Config().get("normal_max_rp"))
            self.maxThrust.setValue(Config().get("normal_max_thrust"))
            self.minThrust.setValue(Config().get("normal_min_thrust"))
            self.slewEnableLimit.setValue(Config().get("normal_slew_limit"))
            self.thrustLoweringSlewRateLimit.setValue(
                Config().get("normal_slew_rate"))
            self.maxYawRate.setValue(Config().get("normal_max_yaw"))
        if (item == 1):  # Advanced
            self.maxAngle.setValue(Config().get("max_rp"))
            self.maxThrust.setValue(Config().get("max_thrust"))
            self.minThrust.setValue(Config().get("min_thrust"))
            self.slewEnableLimit.setValue(Config().get("slew_limit"))
            self.thrustLoweringSlewRateLimit.setValue(
                Config().get("slew_rate"))
            self.maxYawRate.setValue(Config().get("max_yaw"))
            self.isInCrazyFlightmode = True

        if (item == 0):
            newState = False
        else:
            newState = True
        self.maxThrust.setEnabled(newState)
        self.maxAngle.setEnabled(newState)
        self.minThrust.setEnabled(newState)
        self.thrustLoweringSlewRateLimit.setEnabled(newState)
        self.slewEnableLimit.setEnabled(newState)
        self.maxYawRate.setEnabled(newState)

    def _assist_mode_changed(self, item):
        if (item == 0):  # Altitude hold
            self.mode = JoystickReader.ASSISTED_CONTROL_ALTHOLD
        if (item == 1):  # Position hold
            selfmode = JoystickReader.ASSISTED_CONTROL_POSHOLD
        if (item == 2):  # Position hold
            selfmode = JoystickReader.ASSISTED_CONTROL_HEIGHTHOLD
        if (item == 3):  # Position hold
            selfmode = JoystickReader.ASSISTED_CONTROL_HOVER

        self.helper.inputDeviceReader.set_assisted_control(item)
        self.mode_assist = item
        if self.concted : Config().set("assistedControl", item)

    def _basculeur(self, value) :
        if self.concted and value :
            if self._bascule : self._bascule = False
            else : self._bascule = True
            self.set_cf_assist(self._bascule)

    def set_cf_assist(self, value) :
        if self.concted :
            if value : s = "1"
            else : s = "0"
            try :
                self.helper.cf.param.set_value("flightmode.althold", s)
            except KeyError as e:
                logger.warning(str(e))
                return
            except AttributeError as e:
                logger.warning(str(e))
                return

    def _ok_assisted(self, name, value) :
        if self.concted and name == "flightmode.althold" :
            if value == "1" : self.assisted = True
            else : self.assisted = False
            self._bascule = self.assisted
            self.thrustProgress.setEnabled(not self.assisted)
            self.targetThrust.setEnabled(not self.assisted)
            self.helper.inputDeviceReader.isAssisted = self.assisted
            self.checkAssisted.setChecked(self.assisted)
            self.helper.inputDeviceReader.set_assisted_control(self.mode_assist)
            self.helper.inputDeviceReader.assisted_set_local(self.assisted)
            if not self.assisted: 
                self.targetHeight.setText("Not Set")
####                self.ai.setHover(0, self.is_visible())
            else :
                self.thrustProgress.setValue(0)
                self.targetHeight.setVisible(True)
                self.targetHeight.setEnabled(True)
                self.targetHeight.setText(("%.2f meter" % self.height))
####                    self.ai.setHover(self.height+self.estimated_z, self.is_visible())


    @pyqtSlot(bool)
    def changeXmode(self, checked):
        self.helper.cf.commander.set_client_xmode(checked)
        Config().set("client_side_xmode", checked)
        logger.info("Clientside X-mode enabled: %s", checked)

    def _althold_mode_updated(self, state) :
        if state :
            self.helper.inputDeviceReader.connected()
        else : 
            self.helper.inputDeviceReader.disconnected()
        


    def alt1_updated(self, state):
        if state:
            new_index = (self._ring_effect+1) % (self._ledring_nbr_effects+1)
            self.helper.cf.param.set_value("ring.effect",
                                           str(new_index))

    def alt2_updated(self, state):
        if state :
            if self.helper.cf.param.values["ring"]["headlightEnable"] == "1" :
                self.helper.cf.param.set_value("ring.headlightEnable", str(0))
            else :
                self.helper.cf.param.set_value("ring.headlightEnable", str(1))

    def alt3_updated(self, state):
        if self._all_sound:
           if state:
            new_index = (self._soundeffect+1) % (self._sound_nbr_effects+1)
            self.helper.cf.param.set_value("sound.effect", str(new_index))
            self._soundeffect = new_index
        else:
           if state:
             self.helper.cf.param.set_value("sound.effect", str(13))
           else:
             self.helper.cf.param.set_value("sound.effect", str(0))

    def _sound_populate_dropdown(self):
        try:
            nbr = int(self.helper.cf.param.values["sound"]["neffect"])
            current = int(self.helper.cf.param.values["sound"]["effect"])
        except KeyError:
            return

        # Used only in alt3_updated function
        self._soundeffect = current
        self._sound_nbr_effects = nbr

        hardcoded_names = {0: "Off",
                           1: "Factory_test",
                           2: "Usb_connect",
                           3: "Usb_disconnec",
                           4: "Chg_done",
                           5: "Low battery",
                           6: "Startup",
                           7: "Calibrated",
                           8: "Range slow",
                           9: "Range fast",
                           10: "Starwars",
                           11: "Valkiries",
                           12: "By-pass",
                           13: "Siren",
                           14: "Tilt"}

#        hardcoded_names = {0: "Éteint",
#                           1: "Essai d'usine",
#                           2: "Avertissement de connexion USB",
#                           3: "Avertissement de déconnexion USB",
#                           4: "Changement effectué",
#                           5: "Niveau bas de batterie",
#                           6: "Démarrage",
#                           7: "Calibration terminée",
#                           8: "Lent",
#                           9: "Rapide",
#                           10: "Guerre des étoiles",
#                           11: "Walkiries",
#                           12: "Court-circuit",
#                           13: "Sirène",
#                           14: "Inclinaison"}

        for i in range(nbr + 1):
            name = "{}: ".format(i)
            if i in hardcoded_names:
                name += hardcoded_names[i]
            else:
                name += "N/A"
            self._sound_effect.addItem(name, i)

        self._sound_effect.currentIndexChanged.connect(
            self._sound_effect_changed)

        self._sound_effect.setCurrentIndex(0)
        if self.helper.cf.mem.ow_search(vid=0xBC, pid=0x04):
            if self._all_sound : self._sound_effect.setEnabled(True)
            self._sound_all.setEnabled(True)
            self.helper.inputDeviceReader.alt3_updated.add_callback(
                self.alt3_updated)

    def _sound_effect_changed(self, index):
#        if self._all_sound : self._sound_effect.setCurrentIndex(index)
#        el
        self._sound_effect.setCurrentIndex(int(index))
        if index > -1 :
            i = self._sound_effect.itemData(index)
            if i != int(self.helper.cf.param.values["sound"]["effect"]):
                self.helper.cf.param.set_value("sound.effect", str(i))

    def _sound_effect_updated(self, name, value):
        if self.helper.cf.param.is_updated:
            self._sound_effect.setCurrentIndex(int(value))
 
    def _ring_populate_dropdown(self):
        try:
            nbr = int(self.helper.cf.param.values["ring"]["neffect"])
            current = int(self.helper.cf.param.values["ring"]["effect"])
        except KeyError:
            return

        # Used only in alt1_updated function
        self._ring_effect = current
        self._ledring_nbr_effects = nbr

        hardcoded_names = {0: "Off",
                           1: "White spinner",
                           2: "Color spinner",
                           3: "Tilt effect",
                           4: "Brightness effect",
                           5: "Color spinner 2",
                           6: "Double spinner",
                           7: "Solid color effect",
                           8: "Factory test",
                           9: "Battery status",
                           10: "Boat lights",
                           11: "Alert",
                           12: "Gravity",
                           13: "LED tab"}

        for i in range(nbr + 1):
            name = "{}: ".format(i)
            if i in hardcoded_names:
                name += hardcoded_names[i]
            else:
                name += "N/A"
            self._led_ring_effect.addItem(name, i)

        self._led_ring_effect.currentIndexChanged.connect(
            self._ring_effect_changed)

        self._led_ring_effect.setCurrentIndex(0)
        if self.helper.cf.mem.ow_search(vid=0xBC, pid=0x01):
            self._led_ring_effect.setEnabled(True)
            self.helper.cf.param.set_value("ring.headlightEnable", str(0))
            self.helper.inputDeviceReader.alt1_updated.add_callback(
                self.alt1_updated)
            self.helper.inputDeviceReader.alt2_updated.add_callback(
                self.alt2_updated)
            self._led_ring_headlight.setEnabled(True)

    def _ring_effect_changed(self, index):
        self._ring_effect = index
        if index > -1:
            i = self._led_ring_effect.itemData(index)
            logger.debug("Changed effect to {}".format(i))
            if i != int(self.helper.cf.param.values["ring"]["effect"]):
                self.helper.cf.param.set_value("ring.effect", str(i))

    def _ring_effect_updated(self, name, value):
        if self.helper.cf.param.is_updated:
            self._led_ring_effect.setCurrentIndex(int(value))

    def _populate_assisted_mode_dropdown(self):
        self._assist_mode_combo.addItem("Altitude hold", 0)
        self._assist_mode_combo.addItem("Position hold", 1)
        self._assist_mode_combo.addItem("Height hold", 2)
        self._assist_mode_combo.addItem("Hover", 3)
        heightHoldPossible = False
        hoverPossible = False
        assistmodeComboIndex = 0
#### pas de cas poshold
        self._assist_mode_combo.model().item(1).setEnabled(False)
        
        if self.helper.cf.mem.ow_search(vid=0xBC, pid=0x09):
            heightHoldPossible = True

        if self.helper.cf.mem.ow_search(vid=0xBC, pid=0x0A):
            heightHoldPossible = True
            hoverPossible = True
        
        if not heightHoldPossible:
            self._assist_mode_combo.model().item(2).setEnabled(False)
        else:
            self._assist_mode_combo.model().item(0).setEnabled(False)

        if not hoverPossible:
            self._assist_mode_combo.model().item(3).setEnabled(False)
        else:
            self._assist_mode_combo.model().item(0).setEnabled(False)

        self._assist_mode_combo.currentIndexChanged.connect(
            self._assist_mode_changed)
        self._assist_mode_combo.setEnabled(True)

        try:
            assistmodeComboIndex = Config().get("assistedControl")
            logger.info('Mode {}'.format(assistmodeComboIndex))
            if assistmodeComboIndex == 3 and not hoverPossible:
                assistmodeComboIndex = 0
            elif assistmodeComboIndex == 0 and hoverPossible:
                assistmodeComboIndex = 3
            elif assistmodeComboIndex == 2 and not heightHoldPossible:
                assistmodeComboIndex = 0
            elif assistmodeComboIndex == 0 and heightHoldPossible:
                assistmodeComboIndex = 2
            self._assist_mode_combo.setCurrentIndex(assistmodeComboIndex)
            self._assist_mode_combo.currentIndexChanged.emit(
                                                    assistmodeComboIndex)

        except KeyError:
            defaultOption = 0
            if hoverPossible:
                defaultOption = 3
            elif heightHoldPossible:
                defaultOption = 2
            self._assist_mode_combo.setCurrentIndex(defaultOption)
            self._assist_mode_combo.currentIndexChanged.emit(defaultOption)
        self.mode_assist = assistmodeComboIndex
        Config().set("assistedControl", assistmodeComboIndex)

