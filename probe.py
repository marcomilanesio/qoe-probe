#!/usr/bin/python
import sys
import os
import logging
import logging.config
from probe.Configuration import Configuration
from probe.FFLauncher import FFLauncher
from probe.DBClient import DBClient

logging.config.fileConfig('probe/logging.conf')

if __name__ == '__main__':
    if len(sys.argv) < 3:
        exit("Usage: %s %s %s" % (sys.argv[0], 'nr_runs', 'conf_file'))
    nun_runs = int(sys.argv[1])
    conf_file = sys.argv[2]
    logger = logging.getLogger('probe')
    config = Configuration(conf_file)
    plugin_out_file = config.get_database_configuration()['pluginoutfile']
    ff_launcher = FFLauncher(config)
    dbcli = DBClient(config)
    dbcli.create_tables()
    logger.debug('Starting nr_runs (%d)' % nun_runs)
    for i in range(nun_runs):
        stats = ff_launcher.browse_urls()
        if not os.path.exists(plugin_out_file):
            logger.error('Plugin outfile missing.')
            exit("Plugin outfile missing.")
        dbcli.load_to_db(stats)
        logger.debug('Ended browsing run n.%d' % i)
        os.rename(plugin_out_file, plugin_out_file + '.run%d' % i)
        logger.debug('Saved plugin file for run n.%d' % i)
        
