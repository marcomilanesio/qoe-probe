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
import threading
import os
import re

logger = logging.getLogger('FFLauncher')


class BrowserThread(threading.Thread):
    def __init__(self, cmd, outf, errf):
        self.cmd = cmd
        self.process = 0
        self.outfile = outf
        self.errfile = errf
        self.mem = -1
        self.cpu = -1
        self.flag = False

    def run(self, timeout):
        def target():
            o = open(self.outfile, 'a')
            e = open(self.errfile, 'a')
            logger.debug('Browsing Thread started')
            FNULL = open(os.devnull, 'w')
            self.process = subprocess.Popen(self.cmd, stdout=FNULL, stderr=e, shell=True)
            memtable = []
            cputable = []
            while self.process.poll() is None:
                arr = psutil.cpu_percent(interval=0.1, percpu=True)
                cputable.append(sum(arr) / float(len(arr)))
                memtable.append(psutil.virtual_memory().percent)
                time.sleep(1)
            #if self.process.poll() == 0:
            self.mem = float(sum(memtable) / len(memtable))
            self.cpu = float(sum(cputable) / len(cputable))
            #print 'mem = %.2f, cpu = %.2f' % (self.mem, self.cpu)
            #else:
                #logger.error('Browsing thread mem and cpu not set')            
            logger.debug('Browsing Thread finished')
            o.close()
            e.close()

        thread = threading.Thread(target=target)
        thread.start()

        thread.join(timeout)
        if thread.is_alive():
            logger.debug('Timeout expired: terminating process')
            self.process.terminate()
            self.flag = True
            thread.join()
        
        return self.flag, self.mem, self.cpu
                

class FFLauncher():
    def __init__(self, config):
        self.config = config
        self.ffconfig = self.config.get_firefox_configuration()
        self.osstats = {}
        logger.debug('Loaded configuration')

    def browse_urls(self):
        for url in open(self.ffconfig['urlfile']):
            if not re.match('http://', url):
                use = 'http://' + url.strip()
            else:
                use = url.strip()
            if use[-1] != '\/':
                use += '/'
            self.osstats[use] = self._browse_url(use)

        return self.osstats

    def _browse_url(self, url):
        #out = open(self.config['logfile'], 'a')
        logger.info('Browsing %s', url)
        res = {'mem': 0.0, 'cpu': 0.0}
        cmdstr = "xvfb-run --wait=0 %s/firefox -P %s -url %s" % (self.ffconfig['dir'], self.ffconfig['profile'], url)
        cmd = BrowserThread(cmdstr, self.ffconfig['thread_outfile'], self.ffconfig['thread_errfile'])
        t = int(self.ffconfig['thread_timeout'])
        flag, mem, cpu = cmd.run(timeout=t)

        if not flag:
            res['mem'] = mem
            res['cpu'] = cpu
            logger.info('%s: mem = %.2f, cpu = %.2f' % (url, res['mem'], res['cpu']))
        else:
            logger.warning('Problems in browsing thread. Waiting for xvfb to restart...')
            time.sleep(5)
        #out.close()
        return res

    '''
    def dump_data_on_error(self):
        import datetime
        import time
        now = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        dumpfile = './dumped.plugin.file.%s' % now
        plugin_file = self.config.get_database_configuration()['pluginoutfile']
        #os.rename(plugin_file, dumpfile)
        logger.info('Dumped plugin out file to: %s' % dumpfile)
        logger.info('Sleeping 5 seconds...')
        time.sleep(5)
        
        return None
    '''
        
if __name__ == '__main__':
    f = FFLauncher()
    print f.browse_urls()
