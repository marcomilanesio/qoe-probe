#
# mPlane QoE Probe
#
# (c) 2013-2014 mPlane Consortium (http://www.ict-mplane.eu)
#               Author: Salvatore Balzano <balzano@eurecom.fr>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.
#
import subprocess
import threading
import sys
import socket
import struct
import re
import os
from TracerouteParser import TracerouteParser
import json
from DBClient import DBClient
import Utils
from Configuration import Configuration
from JSONClient import JSONClient
import logging
import logging.config

class TstatLiveCapture():
    def __init__(self, config):
        self.tstatconfig = config.get_tstat_configuration()
        self.tstatpid = 0
        logger.debug('Loaded configuration')

    def start(self):
	logger.info('Starting Tstat Live Capture')
	out = open(self.tstatconfig['logfile'], 'a')
	# sudo ./tstat/tstat -i eth2  -l -u -E 1500 -N tstat-conf/net.conf -s /home/linaro/
	cmdstr = "%s/tstat/tstat -i %s -l -u -E 1500 -N %s -s %s" % (self.tstatconfig['dir'], self.tstatconfig['netinterface'], 
								self.tstatconfig['netfile'], self.tstatconfig['logfolder'])
	logger.info(cmdstr)
	proc = subprocess.Popen(cmdstr.split(), stdout=out, stderr=subprocess.PIPE)

    def stop(self):
	logger.info('Stopping Tstat Live Capture')

def main(conf_file):
    config = Configuration(conf_file)
    tstat = TstatLiveCapture(config)
    if sys.argv[1] == "start":
	tstat.start()
    elif sys.argv[1] == "stop":
	tstat.stop()
    else:
	logger.debug('Wrong command ! Only "start" or "stop" are accepted')
    logger.info('Probing starting...')
    #cli = JSONClient(config)
    #cli.prepare_and_send()
    
if __name__ == "__main__":
    if len(sys.argv) != 3:
        exit("%s: You MUST specify a config file" % sys.argv[0])
    logging.config.fileConfig('logging.conf')
    logger = logging.getLogger('TstatLiveCapture')
    conf_file = sys.argv[2]
    main(conf_file)
