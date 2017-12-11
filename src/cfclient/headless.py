# -*- coding: utf-8 -*-
#
#     ||          ____  _ __
#  +------+      / __ )(_) /_______________ _____  ___
#  | 0xBC |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
#  +------+    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
#   ||  ||    /_____/_/\__/\___/_/   \__,_/ /___/\___/
#
#  Copyright (C) 2013 Bitcraze AB
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
Headless client for the Crazyflie.
"""
import logging
import os
import signal
import sys

import cfclient.utils
import cflib.crtp
from cfclient.utils.input import JoystickReader
from cflib.crazyflie import Crazyflie

if os.name == 'posix':
    print('Désactivation des sorties standard des librairies !')
    stdout = os.dup(1)
    os.dup2(os.open('/dev/null', os.O_WRONLY), 1)
    sys.stdout = os.fdopen(stdout, 'w')

# set SDL to use the dummy NULL video driver,
#   so it doesn't need a windowing system.
os.environ["SDL_VIDEODRIVER"] = "dummy"


class HeadlessClient():
    """Crazyflie headless client"""

    def __init__(self):
        """Initialize the headless client and libraries"""
        cflib.crtp.init_drivers()

        self._jr = JoystickReader(do_device_discovery=False)

        self._cf = Crazyflie(ro_cache=None,
                             rw_cache=cfclient.config_path + "/cache")

        signal.signal(signal.SIGINT, signal.SIG_DFL)

        self._devs = []

        for d in self._jr.available_devices():
            self._devs.append(d.name)

    def setup_controller(self, input_config, input_device=0, xmode=False):
        """Set up the device reader"""
        # Set up the joystick reader
        self._jr.device_error.add_callback(self._input_dev_error)
        print("X mode, côté client : %s" % xmode)
        if (xmode):
            self._cf.commander.set_client_xmode(xmode)

        devs = self._jr.available_devices()  # noqa, is this a bug?
        print("Utilisation de [%s] pour l\'entrée des commandes" % self._devs[input_device])
        self._jr.start_input(self._devs[input_device])
        self._jr.set_input_map(self._devs[input_device], input_config)

    def controller_connected(self):
        """ Return True if a controller is connected"""
        return True if (len(self._jr.available_devices()) > 0) else False

    def list_controllers(self):
        """List the available controllers and input mapping"""
        print("\nContrôleurs existants :")
        for i, dev in enumerate(self._devs):
            print(" - contrôleurs #{}: {}".format(i, dev))
        print("\nProfils de contrôleurs existants :")
        for map in os.listdir(cfclient.config_path + '/input'):
            print(" - " + map.split(".json")[0])

    def connect_crazyflie(self, link_uri):
        """Connect to a Crazyflie on the given link uri"""
        self._cf.connection_failed.add_callback(self._connection_failed)
        # 2014-11-25 chad: Add a callback for when we have a good connection.
        self._cf.connected.add_callback(self._connected)
        self._cf.param.add_update_callback(
            group="imu_sensors", name="HMC5883L", cb=(
                lambda name, found: self._jr.set_alt_hold_available(
                    eval(found))))
        self._jr.assisted_control_updated.add_callback(
            lambda enabled: self._cf.param.set_value("flightmode.althold",
                                                     enabled))

        self._cf.open_link(link_uri)
        self._jr.input_updated.add_callback(self._cf.commander.send_setpoint)

    def _connected(self, link):
        """Callback for a successful Crazyflie connection."""
        print("Connecté à {}".format(link))

    def _connection_failed(self, link, message):
        """Callback for a failed Crazyflie connection"""
        print("Échec de la connexion sur {}: {}".format(link, message))
        sys.exit(-1)

    def _input_dev_error(self, message):
        """Callback for an input device error"""
        print("Erreur dans la lecture du périphérique : {}".format(message))
        sys.exit(-1)


def main():
    """Main Crazyflie headless application"""
    import argparse

    parser = argparse.ArgumentParser(prog="cfheadless")
    parser.add_argument("-u", "--uri", action="store", dest="uri", type=str,
                        default="radio://0/80/250K",
                        help="URI à utiliser pour la connexion à la clé de Crazyradio"
                             ", defauts : radio://0/80/250K")
    parser.add_argument("-i", "--input", action="store", dest="input",
                        type=str, default="xbox360_nexon",
                        help="profil à utiliser pour le contrôleur,"
                             "defauts : xbox360_nexon")
    parser.add_argument("-d", "--debug", action="store_true", dest="debug",
                        help="activer la sortie de débogage")
    parser.add_argument("-c", "--controller", action="store", type=int,
                        dest="controller", default=0,
                        help="Utiliser le contrôleur avec une ID spécifique,"
                             " id defaults to 0")
    parser.add_argument("--controllers", action="store_true",
                        dest="list_controllers",
                        help="Affichage seulement des contrôleurs puis sortie")
    parser.add_argument("-x", "--x-mode", action="store_true",
                        dest="xmode",
                        help="Activer X-mode côté client")
    (args, unused) = parser.parse_known_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    headless = HeadlessClient()

    if (args.list_controllers):
        headless.list_controllers()
    else:
        if headless.controller_connected():
            headless.setup_controller(input_config=args.input,
                                      input_device=args.controller,
                                      xmode=args.xmode)
            headless.connect_crazyflie(link_uri=args.uri)
        else:
            print("Pas d\'appareil d\'entrée connecté, sortie !")


if __name__ == "__main__":
    main()
