#!/usr/bin/python
#
# mPlane QoE Probe
#
# (c) 2013-2014 mPlane Consortium (http://www.ict-mplane.eu)
#               Author: Marco Milanesio <milanesio.marco@gmail.com>
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
import psutil
import time
from probe.Configuration import Configuration
import logging

logger = logging.getLogger('FFLauncher')

class FFLauncher():
    def __init__(self, config):
        self.ffconfig = config.get_firefox_configuration()
        self.osstats = {}
        logger.debug('Loaded configuration')

    def browse_urls(self):
        out = open(self.ffconfig['logfile'], 'a')
        for line in open(self.ffconfig['urlfile']):
            logger.info('Browsing %s' % line.strip())
            k = 'http://%s/' % line.strip()
            self.osstats[k] = {'mem': 0.0, 'cpu': 0.0}
            SLICE_IN_SECONDS = 1
            cmdstr = "xvfb-run %s/firefox -P %s -url %s" % (self.ffconfig['dir'], self.ffconfig['profile'], line)
            proc = subprocess.Popen(cmdstr.split(), stdout=out, stderr=subprocess.PIPE)
            memtable = []
            cputable = []
            while proc.poll() == None:
                arr = psutil.cpu_percent(interval=0.1,percpu=True)
                cputable.append(sum(arr) / float(len(arr)))
                memtable.append(psutil.virtual_memory().percent)
                time.sleep(SLICE_IN_SECONDS)
            self.osstats[k]['mem'] = float(sum(memtable) / len(memtable))
            self.osstats[k]['cpu'] = float(sum(cputable) / len(cputable))
            logger.info('mem = %.2f, cpu = %.2f' % (self.osstats[k]['mem'], self.osstats[k]['cpu'])) 
        out.close()
        return self.osstats

if __name__ == '__main__':
    f = FFLauncher()
    print f.browse_urls()
