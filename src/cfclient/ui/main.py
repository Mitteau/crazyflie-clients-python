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
#  this program; if not, write to the Free Software Foundation, Inc., 51
#  Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""
The main file for the Crazyflie control application.
"""
import logging
import sys
import time ####

import cfclient
import cfclient.ui.tabs
import cfclient.ui.toolboxes
import cflib.crtp
from cfclient.ui.dialogs.about import AboutDialog
from cfclient.ui.dialogs.bootloader import BootloaderDialog
from cfclient.utils.config import Config
from cfclient.utils.config_manager import ConfigManager
from cfclient.utils.input import JoystickReader
from cfclient.utils.logconfigreader import LogConfigReader
from cfclient.utils.zmq_led_driver import ZMQLEDDriver
from cfclient.utils.zmq_param import ZMQParamAccess
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.mem import MemoryElement
from PyQt5 import QtWidgets
from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QDir
from PyQt5.QtCore import QThread
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QActionGroup
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QMessageBox

from .dialogs.cf1config import Cf1ConfigDialog
from .dialogs.cf2config import Cf2ConfigDialog
from .dialogs.inputconfigdialogue import InputConfigDialogue
from .dialogs.logconfigdialogue import LogConfigDialogue

__author__ = 'Bitcraze AB'
__all__ = ['MainUI']

logger = logging.getLogger(__name__)

INTERFACE_PROMPT_TEXT = 'Select an interface'

(main_window_class,
 main_windows_base_class) = (uic.loadUiType(cfclient.module_path +
                                            '/ui/main.ui'))


class MyDockWidget(QtWidgets.QDockWidget):
    closed = pyqtSignal()

    def closeEvent(self, event):
        super(MyDockWidget, self).closeEvent(event)
        self.closed.emit()


class UIState:
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    SCANNING = 3


class BatteryStates:
    BATTERY, CHARGING, CHARGED, LOW_POWER = list(range(4))


COLOR_BLUE = '#3399ff'
COLOR_GREEN = '#00ff60'
COLOR_RED = '#cc0404'


def progressbar_stylesheet(color):
    return """
        QProgressBar {
            border: 1px solid #333;
            background-color: transparent;
        }

        QProgressBar::chunk {
            background-color: """ + color + """;
        }
    """


class MainUI(QtWidgets.QMainWindow, main_window_class):
    connectionLostSignal = pyqtSignal(str, str)
    connectionInitiatedSignal = pyqtSignal(str)
    batteryUpdatedSignal = pyqtSignal(int, object, object)
    connectionDoneSignal = pyqtSignal(str)
    connectionFailedSignal = pyqtSignal(str, str)
    disconnectedSignal = pyqtSignal(str)
    linkQualitySignal = pyqtSignal(int)

    _input_device_error_signal = pyqtSignal(str)
    _input_discovery_signal = pyqtSignal(object)
    _log_error_signal = pyqtSignal(object, str)

    def __init__(self, *args):
        super(MainUI, self).__init__(*args)
        self.setupUi(self)

        # Restore window size if present in the config file
        try:
            size = Config().get("window_size")
            self.resize(size[0], size[1])
        except KeyError:
            pass

        ######################################################
        # By lxrocks
        # 'Skinny Progress Bar' tweak for Yosemite
        # Tweak progress bar - artistic I am not - so pick your own colors !!!
        # Only apply to Yosemite
        ######################################################
        import platform

        if platform.system() == 'Darwin':

            (Version, junk, machine) = platform.mac_ver()
            logger.info("This is a MAC - checking if we can apply Progress "
                        "Bar Stylesheet for Yosemite Skinny Bars ")
            yosemite = (10, 10, 0)
            tVersion = tuple(map(int, (Version.split("."))))

            if tVersion >= yosemite:
                logger.info("Found Yosemite - applying stylesheet")

                tcss = """
                    QProgressBar {
                        border: 1px solid grey;
                        border-radius: 5px;
                        text-align: center;
                    }
                    QProgressBar::chunk {
                        background-color: """ + COLOR_BLUE + """;
                    }
                 """
                self.setStyleSheet(tcss)

            else:
                logger.info("Pre-Yosemite - skinny bar stylesheet not applied")

        ######################################################

        self.cf = Crazyflie(ro_cache=None,
                            rw_cache=cfclient.config_path + "/cache")

        cflib.crtp.init_drivers(enable_debug_driver=Config()
                                .get("enable_debug_driver"))

        zmq_params = ZMQParamAccess(self.cf)
        zmq_params.start()

        zmq_leds = ZMQLEDDriver(self.cf)
        zmq_leds.start()

        self.scanner = ScannerThread()
        self.scanner.interfaceFoundSignal.connect(self.foundInterfaces)
        self.scanner.start()

        # Hide the 'File' menu on OS X, since its only item, 'Exit', gets
        # merged into the application menu.
        if sys.platform == 'darwin':
            self.menuFile.menuAction().setVisible(False)

##############################################################################
#                                                                            #
#   ZONE INPUT CONTROL INIT                                                  #
#                                                                            #
##############################################################################

        self.joystickReader = JoystickReader()
        cfclient.ui.pluginhelper.inputDeviceReader = self.joystickReader

        # References to all the device sub-menus in the "Input device" menu
        self._all_role_menus = ()
        # Used to filter what new devices to add default mapping to
        self._available_devices = ()
        # Keep track of mux nodes so we can enable according to how many
        # devices we have
        self._all_mux_nodes = ()

        # Check which Input muxes are available
        self._mux_group = QActionGroup(self._menu_inputdevice, exclusive=True)
        for m in self.joystickReader.available_mux():
            node = QAction(m.name,
                           self._menu_inputdevice,
                           checkable=True,
                           enabled=False)
            node.toggled.connect(self._mux_selected)
            self._mux_group.addAction(node)
            self._menu_inputdevice.addAction(node)
            self._all_mux_nodes += (node,)
            mux_subnodes = ()
            for name in m.supported_roles():
                sub_node = QMenu("    {}".format(name),
                                 self._menu_inputdevice,
                                 enabled=False)
                self._menu_inputdevice.addMenu(sub_node)
                mux_subnodes += (sub_node,)
                self._all_role_menus += ({"muxmenu": node,
                                          "rolemenu": sub_node},)
            node.setData((m, mux_subnodes))


####        for m in self._all_role_menus : ####
####            logger.info("_all_roles_menus, mux >{}<, role >{}<".format(m["muxmenu"].text(), m["rolemenu"].title().strip())) ####
        self._mapping_support = True
        self._device = None
        self.selected_mapping = None
        self._role = ""
####        self.first_show = True

        # Create and start the Input Reader
        self._statusbar_label = QLabel("No input-device found, insert one to"
                                       " fly.")
        self.statusBar().addWidget(self._statusbar_label)

        self._active_device = ""
        # self.configGroup = QActionGroup(self._menu_mappings, exclusive=True)

        self._mux_group = QActionGroup(self._menu_inputdevice, exclusive=True) #### ????

        self.joystickReader.device_error.add_callback(
            self._input_device_error_signal.emit)
        self._input_device_error_signal.connect(
            self._display_input_device_error)

        self.joystickReader.device_discovery.add_callback(
            self._input_discovery_signal.emit)
        self._input_discovery_signal.connect(self.device_discovery)

        self.joystickReader.input_updated.add_callback(
            lambda *args: self._disable_input or
            self.cf.commander.send_setpoint(*args))

        self.joystickReader.assisted_input_updated.add_callback(
            lambda *args: self._disable_input or
            self.cf.commander.send_velocity_world_setpoint(*args))

        self.joystickReader.heighthold_input_updated.add_callback(
            lambda *args: self._disable_input or
            self.cf.commander.send_zdistance_setpoint(*args))

        self.joystickReader.hover_input_updated.add_callback( #### À voir ????
            self.cf.commander.send_hover_setpoint)

        self._current_input_config = None
        self._active_config = None

        self.inputConfig = None
        
        self._stop_input = False
        self._first_run = True
        self.start = True

        # recover saved mux input configuration
        self.mux_name = ""
        self.device_input = ""
        self.teacher_input = ""
        self.student_input = ""
        self.possible = False
        self.mappings = {"": None}
        self.input_config_clear = False
        self.nb_devices = 0
        self.devs = []
        self._device_is_selected = False

        try:
            self.mux_name = Config().get("mux_name")
            for m in self._all_mux_nodes:
####                logger.info("self._all_mux_nodes[i] {}".format(m.text()))
                if m.text() == self.mux_name : self.possible = True
            if self.possible :
                if self.mux_name == "Normal" :
                    self.device_input = Config().get("input_device")
                elif self.mux_name == "Teacher (RP)" or self.mux_name == "Teacher (RPYT)" :
                    self.teacher_input = Config().get("input_teacher")
                    self.student_input = Config().get("input_student")
            else :
                self.mux_name = "Normal"
                self.device_input = ""
                self.teacher_input = ""
                self.student_input = ""
####                Config().set("mux_name", str(self.mux_name))


            self.mappings = Config().get("device_config_mapping")
####            logger.info("Mappings {}".format(self.mappings))
####            for k in self.mappings.keys() : logger.info("Key {}, say {}".format(k, self.mappings[k])) #### ok ici

        except Exception as e:
            logger.warning("Exception reading mux config [{}]".format(e))

        # Connect UI signals
        self.menuItemConfInputDevice.triggered.connect(
            self._show_input_device_config_dialog)
####        self._menuitem_rescandevices.triggered.connect(self._rescan_devices)
        self._menuItem_openconfigfolder.triggered.connect(
            self._open_config_folder)


##############################################################################
#                                                                            #
#   FIN DE ZONE INPUT CONTROL INIT                                           #
#                                                                            #
##############################################################################

        # TODO: Need to reload configs
        # ConfigManager().conf_needs_reload.add_callback(self._reload_configs)

        self.connect_input = QShortcut("Ctrl+I", self.connectButton, self._connect)
        self.cf.connection_failed.add_callback(
            self.connectionFailedSignal.emit)
        self.connectionFailedSignal.connect(self._connection_failed)

        # Connect UI signals
        self.logConfigAction.triggered.connect(self._show_connect_dialog)
        self.interfaceCombo.currentIndexChanged['QString'].connect(
            self.interfaceChanged)
        self.connectButton.clicked.connect(self._connect)
        self.scanButton.clicked.connect(self._scan)
        self.menuItemConnect.triggered.connect(self._connect)
        self.menuItemExit.triggered.connect(self.closeAppRequest)
        self.batteryUpdatedSignal.connect(self._update_battery)

        self.address.setValue(0xE7E7E7E7E7)

        self._auto_reconnect_enabled = Config().get("auto_reconnect")
        self.autoReconnectCheckBox.toggled.connect(
            self._auto_reconnect_changed)
        self.autoReconnectCheckBox.setChecked(Config().get("auto_reconnect"))

        self._disable_input = False

        # Connection callbacks and signal wrappers for UI protection
        self.cf.connected.add_callback(self.connectionDoneSignal.emit)
        self.connectionDoneSignal.connect(self._connected)
        self.cf.disconnected.add_callback(self.disconnectedSignal.emit)
        self.disconnectedSignal.connect(self._disconnected)
        self.cf.connection_lost.add_callback(self.connectionLostSignal.emit)
        self.connectionLostSignal.connect(self._connection_lost)
        self.cf.connection_requested.add_callback(
            self.connectionInitiatedSignal.emit)
        self.connectionInitiatedSignal.connect(self._connection_initiated)
        self._log_error_signal.connect(self._logging_error)

        self.batteryBar.setTextVisible(False)
        self.batteryBar.setStyleSheet(progressbar_stylesheet(COLOR_BLUE))

        self.linkQualityBar.setTextVisible(False)
        self.linkQualityBar.setStyleSheet(progressbar_stylesheet(COLOR_BLUE))

        # Connect link quality feedback
        self.cf.link_quality_updated.add_callback(self.linkQualitySignal.emit)
        self.linkQualitySignal.connect(
            lambda percentage: self.linkQualityBar.setValue(percentage))

        self._selected_interface = None
        self._initial_scan = True
        self._scan()

        # Parse the log configuration files
        self.logConfigReader = LogConfigReader(self.cf)

        # Add things to helper so tabs can access it
        cfclient.ui.pluginhelper.cf = self.cf
        cfclient.ui.pluginhelper.logConfigReader = self.logConfigReader
        cfclient.ui.pluginhelper.mainUI = self

        self.logConfigDialogue = LogConfigDialogue(cfclient.ui.pluginhelper)
        self._bootloader_dialog = BootloaderDialog(cfclient.ui.pluginhelper)
        self._cf2config_dialog = Cf2ConfigDialog(cfclient.ui.pluginhelper)
        self._cf1config_dialog = Cf1ConfigDialog(cfclient.ui.pluginhelper)
        self.menuItemBootloader.triggered.connect(self._bootloader_dialog.show)
        self._about_dialog = AboutDialog(cfclient.ui.pluginhelper)
        self.menuItemAbout.triggered.connect(self._about_dialog.show)
        self._menu_cf2_config.triggered.connect(self._cf2config_dialog.show)
        self._menu_cf1_config.triggered.connect(self._cf1config_dialog.show)

        # Load and connect tabs
        self.tabsMenuItem = QMenu("Tabs", self.menuView, enabled=True)
        self.menuView.addMenu(self.tabsMenuItem)

        # self.tabsMenuItem.setMenu(QtWidgets.QMenu())
        tabItems = {}
        self.loadedTabs = []
        for tabClass in cfclient.ui.tabs.available:
            tab = tabClass(self.tabs, cfclient.ui.pluginhelper)
            item = QtWidgets.QAction(tab.getMenuName(), self, checkable=True)
            item.toggled.connect(tab.toggleVisibility)
            self.tabsMenuItem.addAction(item)
            tabItems[tab.getTabName()] = item
            self.loadedTabs.append(tab)
            if not tab.enabled:
                item.setEnabled(False)

        # First instantiate all tabs and then open them in the correct order
        try:
            for tName in Config().get("open_tabs").split(","):
                t = tabItems[tName]
                if (t is not None and t.isEnabled()):
                    # Toggle though menu so it's also marked as open there
                    t.toggle()
        except Exception as e:
            logger.warning("Exception while opening tabs [{}]".format(e))

        # Loading toolboxes (A bit of magic for a lot of automatic)
        self.toolboxesMenuItem = QMenu("Toolboxes", self.menuView,
                                       enabled=True)
        self.menuView.addMenu(self.toolboxesMenuItem)

        self.toolboxes = []
        for t_class in cfclient.ui.toolboxes.toolboxes:
            toolbox = t_class(cfclient.ui.pluginhelper)
            dockToolbox = MyDockWidget(toolbox.getName())
            dockToolbox.setWidget(toolbox)
            self.toolboxes += [dockToolbox, ]

            # Add menu item for the toolbox
            item = QtWidgets.QAction(toolbox.getName(), self)
            item.setCheckable(True)
            item.triggered.connect(self.toggleToolbox)
            self.toolboxesMenuItem.addAction(item)

            dockToolbox.closed.connect(lambda: self.toggleToolbox(False))

            # Setup some introspection
            item.dockToolbox = dockToolbox
            item.menuItem = item
            dockToolbox.dockToolbox = dockToolbox
            dockToolbox.menuItem = item







    def interfaceChanged(self, interface):
        if interface == INTERFACE_PROMPT_TEXT:
            self._selected_interface = None
        else:
            self._selected_interface = interface
        self._update_ui_state()

    def foundInterfaces(self, interfaces):
        selected_interface = self._selected_interface

        self.interfaceCombo.clear()
        self.interfaceCombo.addItem(INTERFACE_PROMPT_TEXT)

        formatted_interfaces = []
        for i in interfaces:
            if len(i[1]) > 0:
                interface = "%s - %s" % (i[0], i[1])
            else:
                interface = i[0]
            formatted_interfaces.append(interface)
        self.interfaceCombo.addItems(formatted_interfaces)

        if self._initial_scan:
            self._initial_scan = False

            try:
                if len(Config().get("link_uri")) > 0:
                    formatted_interfaces.index(Config().get("link_uri"))
                    selected_interface = Config().get("link_uri")
            except KeyError:
                #  The configuration for link_uri was not found
                pass
            except ValueError:
                #  The saved URI was not found while scanning
                pass

        if len(interfaces) == 1 and selected_interface is None:
            selected_interface = interfaces[0][0]

        newIndex = 0
        if selected_interface is not None:
            try:
                newIndex = formatted_interfaces.index(selected_interface) + 1
            except ValueError:
                pass

        self.interfaceCombo.setCurrentIndex(newIndex)

        self.uiState = UIState.DISCONNECTED
        self._update_ui_state()

    def _update_ui_state(self):
        if self.uiState == UIState.DISCONNECTED:
            self.setWindowTitle("Not connected")
            canConnect = self._selected_interface is not None
            self.menuItemConnect.setText("Connect to Crazyflie")
            self.menuItemConnect.setEnabled(canConnect)
            self.connectButton.setText("Connect Ctrl+I")
            self.connectButton.setToolTip(
                "Connect to the Crazyflie on the selected interface")
            self.connectButton.setEnabled(canConnect)
            self.scanButton.setText("Scan")
            self.scanButton.setEnabled(True)
            self.address.setEnabled(True)
            self.batteryBar.setValue(3000)
            self._menu_cf2_config.setEnabled(False)
            self._menu_cf1_config.setEnabled(True)
            self.linkQualityBar.setValue(0)
            self.menuItemBootloader.setEnabled(True)
            self.logConfigAction.setEnabled(False)
            self.interfaceCombo.setEnabled(True)
        elif self.uiState == UIState.CONNECTED:
            s = "Connected on %s" % self._selected_interface
            self.setWindowTitle(s)
            self.menuItemConnect.setText("Disconnect")
            self.menuItemConnect.setEnabled(True)
            self.connectButton.setText("Disconnect Ctrl+I")
            self.connectButton.setToolTip("Disconnect from the Crazyflie")
            self.scanButton.setEnabled(False)
            self.logConfigAction.setEnabled(True)
            # Find out if there's an I2C EEPROM, otherwise don't show the
            # dialog.
            if len(self.cf.mem.get_mems(MemoryElement.TYPE_I2C)) > 0:
                self._menu_cf2_config.setEnabled(True)
            self._menu_cf1_config.setEnabled(False)
        elif self.uiState == UIState.CONNECTING:
            s = "Connecting to {} ...".format(self._selected_interface)
            self.setWindowTitle(s)
            self.menuItemConnect.setText("Cancel")
            self.menuItemConnect.setEnabled(True)
            self.connectButton.setText("Cancel")
            self.connectButton.setToolTip("Cancel connecting to the Crazyflie")
            self.scanButton.setEnabled(False)
            self.address.setEnabled(False)
            self.menuItemBootloader.setEnabled(False)
            self.interfaceCombo.setEnabled(False)
        elif self.uiState == UIState.SCANNING:
            self.setWindowTitle("Scanning ...")
            self.connectButton.setText("Connect Ctrl+I")
            self.menuItemConnect.setEnabled(False)
            self.connectButton.setText("Connect Ctrl+I")
            self.connectButton.setEnabled(False)
            self.scanButton.setText("Scanning...")
            self.scanButton.setEnabled(False)
            self.address.setEnabled(False)
            self.menuItemBootloader.setEnabled(False)
            self.interfaceCombo.setEnabled(False)

    @pyqtSlot(bool)
    def toggleToolbox(self, display):
        menuItem = self.sender().menuItem
        dockToolbox = self.sender().dockToolbox

        if display and not dockToolbox.isVisible():
            dockToolbox.widget().enable()
            self.addDockWidget(dockToolbox.widget().preferedDockArea(),
                               dockToolbox)
            dockToolbox.show()
        elif not display:
            dockToolbox.widget().disable()
            self.removeDockWidget(dockToolbox)
            dockToolbox.hide()
            menuItem.setChecked(False)

    def _update_battery(self, timestamp, data, logconf):
        self.batteryBar.setValue(int(data["pm.vbat"] * 1000))

        color = COLOR_BLUE
        # TODO firmware reports fully-charged state as 'Battery',
        # rather than 'Charged'
        if data["pm.state"] in [BatteryStates.CHARGING, BatteryStates.CHARGED]:
            color = COLOR_GREEN
        elif data["pm.state"] == BatteryStates.LOW_POWER:
            color = COLOR_RED

        self.batteryBar.setStyleSheet(progressbar_stylesheet(color))
        self._aff_volts.setText(("%.3f" % data["pm.vbat"]))

#### ZONE CONNEXION AVEC CF

    def _auto_reconnect_changed(self, checked):
        self._auto_reconnect_enabled = checked
        Config().set("auto_reconnect", checked)
        logger.info("Auto reconnect enabled: {}".format(checked))

    def _show_connect_dialog(self):
        self.logConfigDialogue.show()

    def _connected(self):
        self.uiState = UIState.CONNECTED
        self._update_ui_state()

        Config().set("link_uri", str(self._selected_interface))

        lg = LogConfig("Battery", 1000)
        lg.add_variable("pm.vbat", "float")
        lg.add_variable("pm.state", "int8_t")
        try:
            self.cf.log.add_config(lg)
            lg.data_received_cb.add_callback(self.batteryUpdatedSignal.emit)
            lg.error_cb.add_callback(self._log_error_signal.emit)
            lg.start()
        except KeyError as e:
            logger.warning(str(e))

        mems = self.cf.mem.get_mems(MemoryElement.TYPE_DRIVER_LED)
        if len(mems) > 0:
            mems[0].write_data(self._led_write_done)

    def _disconnected(self):
        self.uiState = UIState.DISCONNECTED
        self._update_ui_state()

    def _connection_initiated(self):
        self.uiState = UIState.CONNECTING
        self._update_ui_state()

    def _led_write_done(self, mem, addr):
        logger.info("LED write done callback")

    def _logging_error(self, log_conf, msg):
        QMessageBox.about(self, "Log error", "Error when starting log config"
                                             " [{}]: {}".format(log_conf.name,
                                                                msg))

    def _connection_lost(self, linkURI, msg):
        if not self._auto_reconnect_enabled:
            if self.isActiveWindow():
                warningCaption = "Communication failure"
                error = "Connection lost to {}: {}".format(linkURI, msg)
                QMessageBox.critical(self, warningCaption, error)
                self.uiState = UIState.DISCONNECTED
                self._update_ui_state()
        else:
            self._connect()

    def _connection_failed(self, linkURI, error):
        if not self._auto_reconnect_enabled:
            msg = "Failed to connect on {}: {}".format(linkURI, error)
            warningCaption = "Communication failure"
            QMessageBox.critical(self, warningCaption, msg)
            self.uiState = UIState.DISCONNECTED
            self._update_ui_state()
        else:
            self._connect()

    def closeEvent(self, event):
        self.hide()
        self.cf.close_link()
        Config().save_file()

    def resizeEvent(self, event):
        Config().set("window_size", [event.size().width(),
                                     event.size().height()])

    def _connect(self):
        if self.uiState == UIState.CONNECTED:
            self.cf.close_link()
        elif self.uiState == UIState.CONNECTING:
            self.cf.close_link()
            self.uiState = UIState.DISCONNECTED
            self._update_ui_state()
        else:
            self.cf.open_link(self._selected_interface)

    def _scan(self):
        self.uiState = UIState.SCANNING
        self._update_ui_state()
        self.scanner.scanSignal.emit(self.address.value())

##############################################################################"
#                                                                            #
#   ZONE INPUT CONTROL                                                       #
#                                                                            #
##############################################################################"

    def _show_input_device_config_dialog(self):
        self.inputConfig = InputConfigDialogue(self.joystickReader) #### fenêtre de configuration d'une manette
        self.inputConfig.show()

    def disable_input(self, disable):
        """
        Disable the gamepad input to be able to send setpoint from a tab
        """
        self._disable_input = disable

    def device_discovery(self, devs):
        """Called when new devices have been added or removed"""
        checked = False
        found = False
        for d in devs : self.devs.append(d)
####        self.devs = devs #### inutile !!!!!!!!!
####        logger.info("Nb devices {}, device enregistré >{}<".format(len( self.devs), self.device_input)) ####passer en debug
        for menu in self._all_role_menus : menu["rolemenu"].clear()
        if len(self.devs) == 0 :#### or nb < self.nb_devices : VÉRIFIER CAS 2 --> 1
            self.joystickReader.set_mux() #### arrêter tout
            Config().set("mux_name", "")
            self._device == None
        else :
            self.joystickReader.set_mux("Normal") #### de là ajouter autres muxes suivant config.json
            Config().set("mux_name", "Normal")
####            logger.info("Nb devices 1 {}<".format(len( self.devs)))
            for d in devs :
                if d.name == self.device_input :
                    self._device = d
                    found = True
####            logger.info("Nb devices 2 {}<".format(len( self.devs)))
            if not found :
                ret = QMessageBox.question(self, "input device error",
                "The input device is a new one.\nRegister it?\n"
                "No will exit client.")
                """
                """
####                logger.info("ret {}".format(ret))
####                ret = 16384
####                logger.info("Nb devices 3 {}<".format(len( self.devs)))
                if ret == 16384 :
                    self._device = d
                    self.device_input = d.name
####                    logger.info("Nb devices 4 {}<".format(len( self.devs)))
                elif ret == 65536 : self.closeAppRequest()
####                logger.info("Nb devices 5 {}<".format(len( self.devs)))
####                    logger.info("Devs choisi {}".format(self._device))
####????                Config().set("input_device", "")
####            logger.info("Dans discvovery Nb devices {}, device enregistré >{}<".format(len( self.devs), self.device_input)) ####passer en debug
            for menu in self._all_role_menus:
                mux_menu = menu["muxmenu"]
                if not checked and mux_menu.text() == "Normal" :
                    mux_menu.setEnabled(True)
                    mux_menu.setChecked(True)
                    checked = True
            
####            logger.info("Dans discvovery {}".format(self._device.name))
####            logger.info("Dans discvovery Nb devices {}, device enregistré >{}<".format(len( self.devs), self.device_input)) ####passer en debug
            self.set_devices_menu( self.devs)
####            logger.info(" On passe au check")
####            self.set_input_mapping_device(devs)
            self.set_input_mapping_device()

    def set_devices_menu(self, devs) : #### correct
        exist = False
        for menu in self._all_role_menus:
            role_menu = menu["rolemenu"]
            mux_menu = menu["muxmenu"]
            dev_group = QActionGroup(role_menu, exclusive=True)
####            nb = len(devs)
####            logger.info("Nb devices {}, device enregistré >{}<".format(nb, self.device_input)) ####passer en debug
            for d in devs :
####                logger.info("devs in set_devices_men {}".format(d.name))
                dev_node = QAction(d.name, role_menu, checkable=True,
                                                    enabled=True)




####                for a in role_menu.actions() : logger.info("Actions {}dans {}, et {}".format(a.text(), mux_menu.text(), role_menu.title()))


                exist = False
                for a in role_menu.actions() :
                    if a.text() == d.name :
                        exist = True
                        break
                if not exist :
                    role_menu.addAction(dev_node)
                    dev_group.addAction(dev_node)
                    dev_node.toggled.connect(self._inputdevice_selected)
                    map_node = None
                    if d.supports_mapping:
                        map_node = QMenu("    Input map", role_menu, enabled=False)
                        map_group = QActionGroup(role_menu, exclusive=True)
                        # Connect device node to map node for easy
                        # enabling/disabling when selection changes and device
                        # to easily enable it
                        dev_node.setData((map_node, d))
                        for c in ConfigManager().get_list_of_configs():
                            node = QAction(c, map_node, checkable=True,
                                                          enabled=True)
                            node.toggled.connect(self._inputconfig_selected)
                            map_node.addAction(node)
                            # Connect all the map nodes back to the device
                            # action node where we can access the raw device
                            node.setData(dev_node)
                            map_group.addAction(node)
                            # If this device hasn't been found before, then
                            # select the default mapping for it.
                            role_menu.addMenu(map_node)
                        dev_node.setData((map_node, d, mux_menu))

                # Update the list of what devices we found
                # to avoid selecting default mapping for all devices when
                # a new one is inserted
            
            self._available_devices = ()
            for d in devs:
                self._available_devices += (d,)
####                logger.info("dans construction du menu, device {}".format(d)) #### correct
        self._update_input_device_footer()

    def set_input_mapping_device(self) :
        node = None
        dev_node = None
        device = self._device
        if device == None :
####            logger.info("No device............. ") #### debug ?
            QMessageBox.warning(self, "Input device error", "This device is not registered.\nPlease select.")
        else :
####            logger.info("Device............. {}".format(device.name))
            if device.name not in self.mappings.keys() :
                device_input_map = ""
                QMessageBox.warning(self, "Input device error", "Have not \
found registered input map\nPlease select one.")
            else :
                device_input_map = self.mappings[device.name]
####        if
####        device_input_map = self.mappings[device.name]
####                logger.info("Device name enregistrés dans set input mapping {}, {}".format(device.name, device_input_map))
                found = False
                for ms in self._all_role_menus : #### ici pour ajouter muxes
                    if ms["muxmenu"].text() == "Normal" and\
                     ms["rolemenu"].title().strip() == "Device" :
                        node = ms["rolemenu"]
####                        logger.info("Node {}".format(node.title()))
####                node.setChecked(True) #### cas muxes
                for a in node.actions() :
####                    logger.info("Dans node choisi {}, device input {}".format(a.text(), device.name))
                    if a.text() == device.name :
####                        logger.info("On va chéquer")
                        a.setChecked(True) #### vérifier device_selected....
####                        logger.info("On a chéqué")
                        dev_node = a
####                        logger.info("Map node {}".format(a.data()[0].title()))
                        dev_node.data()[0].setEnabled(True)
                        found = True
                        break #### rétablir
                if found == False :
                    logger.info("Device not found, in set_input_mapping_device")
####                    QMessageBox.warning(self, "Input device error", "Cannot \
####find registered device\nPlease select one.")
####        else :#### sélectionner une map
####            for d in self.mappings :
####                if d.key() == self.device_input :
####                    device_input_map = d.data()
####            device_input_map = self.mappings[self.device_input]
####           for k in self.mappings.keys() :
####               logger.info("Key: {}, map: {}".format(k, self.mappings[k]))
####               if k == self.device_input :
####                   device_input_map = self.mappings[k]
####                   Config().set("device_input", self.device_input)
####                   break
####                   device_input_map = ""
                else :
####                    logger.info("Found map {}".format(device_input_map))
### cas pas trouvé ?
                    for mp in dev_node.data()[0].actions() :
####                logger.info("maps {}".format(mp.text()))
                        if mp.text() == device_input_map :
                            mp.setChecked(True)
                            if device.name not in self.mappings :
                                self.mappings[device.name] = mp.text()
                        
                        Config().set("device_config_mapping", self.mappings)
####                    Config().set()
####                    input_map_name = mp.text()
        self._update_input_device_footer()

    def _display_input_device_error(self, error):
        
        QMessageBox.warning(self, "Input device error", error+"\nInput stoppé")
####        self.joystickReader.pause_input() #### ????
####        if error == "Error while running input device" :
####            self._inputdevice_selected(True)

        self.cf.close_link() #### Pertinent ? oui


    def _mux_selected(self, checked):
        """Called when a new mux is selected. The menu item contains a
        reference to the raw mux object as well as to the associated device
        sub-nodes"""
        if not checked:
            (mux, sub_nodes) = self.sender().data()
            for s in sub_nodes:
                s.setEnabled(False)
        else:
####            logger.info("On passe dans Mux selection") ####
            (mux, sub_nodes) = self.sender().data()
            for s in sub_nodes:
                s.setEnabled(True)
            self.joystickReader.set_mux(mux=mux)

            # Go though the tree and select devices/mapping that was
            # selected before it was disabled.
            for role_node in sub_nodes:
                for dev_node in role_node.children():
                    if type(dev_node) is QAction and dev_node.isChecked():
                        dev_node.toggled.emit(True)

            self._update_input_device_footer()

    def _get_dev_status(self, device):
        msg = "{}".format(device.name)
####        logger.info("dans get dev status input {}".format(device.input_map)) ####
        if device.supports_mapping:
            map_name = "No input mapping"
            if device.input_map:
                map_name = device.input_map_name
            msg += " ({})".format(map_name)
        return msg

    def _update_input_device_footer(self):
        """Update the footer in the bottom of the UI with status for the
        input device and its mapping"""

        msg = ""

        if len(self.joystickReader.available_devices()) > 0:
            mux = self.joystickReader._selected_mux
            msg = "Using {} mux with ".format(mux.name)
            for key in list(mux._devs.keys())[:-1]:
                if mux._devs[key]:
                    msg += "{}, ".format(self._get_dev_status(mux._devs[key]))
                else:
                    msg += "N/A, "
            # Last item
            key = list(mux._devs.keys())[-1]
            if mux._devs[key]:
                msg += "{}".format(self._get_dev_status(mux._devs[key]))
            else:
                msg += "N/A"
        else:
            msg = "No input device found"
        self._statusbar_label.setText(msg)

    def _inputdevice_selected(self, checked):
        """Called when a new input device has been selected from the menu. The
        data in the menu object is the associated map menu (directly under the
        item in the menu) and the raw device"""
        logger.info("Dans inputdevice_selected")
        node = None
        dev_node = None
        device_input_map = ""
        found = False
        selected_device = str(self.sender().text())
####        logger.info("Sélection {}".format(selected_device))
        (map_menu, device, mux_menu) = self.sender().data()
####        logger.info("En place {}".format(device.name))
        if not checked:
####            logger.info("Pas chéqué")
            if map_menu:
                map_menu.setEnabled(False)
                # Do not close the device, since we don't know exactly
                # how many devices the mux can have open. When selecting a
                # new mux the old one will take care of this.
        else : #### not self._device_is_selected :
####            self._device_is_selected = True
####            self.joystickReader.pause_input() #### ????
            if map_menu:
                map_menu.setEnabled(True)
            (mux, sub_nodes) = mux_menu.data()
            for role_node in sub_nodes:
                for d in role_node.children():
                    if type(d) is QAction and d.isChecked():
                        if device.id == d.data()[1].id \
                                and dev_node is not self.sender():
                            dev_node = d
                        else :
                            time.sleep(20)
                            d.setChecked(False)

####            logger.info("self.sender() 1 {}".format(self.sender()))
            role_in_mux = str(self.sender().parent().title()).strip()
####            logger.info("Role of {} is {}".format(device.name,
####                                                  role_in_mux))
            self._mapping_support = self.joystickReader.start_input(
                device.name,
                role_in_mux)
            self._device = device
            self._role = role_in_mux
            Config().set("input_device", str(device.name))

            if device.name not in self.mappings.keys() or len(self.mappings[device.name]) == 0:
                QMessageBox.warning(self, "Input device error", "No mapping defined.\nPlease select one.")
            else :
                device_input_map = self.mappings[device.name]

                for mp in dev_node.data()[0].actions() :
####                    logger.info("maps {}".format(mp.text()))
                    if mp.text() == device_input_map :
                        mp.setChecked(True)
                        break
####        else : logger.info("un coup pour rien")
        self._update_input_device_footer()

    def _inputconfig_selected(self, checked):
        """Called when a new configuration has been selected from the menu. The
        data in the menu object is a referance to the device QAction in parent
        menu. This contains a referance to the raw device."""
####        logger.info("Dans _inputconfig_selected")
        if not checked:
            return

        devs = []
        device = self.sender().data().data()[1]
        selected_mapping = str(self.sender().text())
        device_input_map = ""
        found = False
        
        """
        for menu in self._all_role_menus:
            role_menu = menu["rolemenu"]
            mux_menu = menu["muxmenu"]
        """


        for ms in self._all_role_menus : #### ici pour ajouter muxes
            if ms["muxmenu"].text() == "Normal" and\
             ms["rolemenu"].title().strip() == "Device" :
                node = ms["rolemenu"]
####                node.setChecked(True) #### cas muxes
        for a in node.actions() :
####            logger.info("Dans node choisi {}, device input {}".format(a.text(), self.device_input))
            if a.text() == device.name :
####                a.setChecked(True) #### vérifier device_selected....!!!!!!!!!!!!!!!!!!!!!!!!
                dev_node = a
####                logger.info("Map node {}".format(a.data()[0].title()))
####                dev_node.data()[0].setEnabled(True)
                found = True
                break
        if found == False : pass ####
####            QMessageBox.warning(self, "Input device error", "Cannot \
####find registered device\nPlease select one.")
        else :#### sélectionner une map
####            for d in self.mappings :
####                if d.key() == self.device_input :
####                    device_input_map = d.data()
####            device_input_map = self.mappings[self.device_input]
           for k in self.mappings.keys() :
####               logger.info("Key: {}, map: {}".format(k, self.mappings[k]))
               if k == device :
                   device_input_map = self.mappings[k]
                   selected_mapping = self.mappings[k]
                   break
                   device_input_map = ""
####           logger.info("Map found {}".format(device_input_map))
####           for mp in dev_node.data()[0].actions() :
####                logger.info("maps {}".format(mp.text()))
####               if mp.text() == selected_mapping :
####                   mp.setChecked(True)
####                   selected_mapping = mp.text()
                   
           if device not in self.mappings.keys() : #### à voir de près
               self.mappings[device.name] = device_input_map

####        logger.info("Semected mappoing''''''''''''{}".format(selected_mapping))
        self.joystickReader.set_input_map(device.name, selected_mapping) ####
        self.selected_mapping = selected_mapping
        self.mappings[device.name] = selected_mapping

        self.device = device

        self._update_input_device_footer()

##############################################################################"
#                                                                            #
#   FIN DE ZONE                                                              #
#                                                                            #
##############################################################################"

    def _open_config_folder(self):
        QDesktopServices.openUrl(
            QUrl("file:///" +
                 QDir.toNativeSeparators(cfclient.config_path)))

    def closeAppRequest(self):
        self.joystickReader.pause_input() #### !!!!
        self.close()
        sys.exit(0)


class ScannerThread(QThread):

    scanSignal = pyqtSignal(object)
    interfaceFoundSignal = pyqtSignal(object)

    def __init__(self):
        QThread.__init__(self)
        self.moveToThread(self)
        self.scanSignal.connect(self.scan)

    def scan(self, address):
        self.interfaceFoundSignal.emit(cflib.crtp.scan_interfaces(address))
