#!/usr/bin/python
import sys
import os
import logging
import logging.config
from probe.Configuration import Configuration
from probe.FFLauncher import FFLauncher
from probe.DBClient import DBClient
from probe.ActiveMeasurement import Monitor
from probe.JSONClient import JSONClient

logging.config.fileConfig('logging.conf')

if __name__ == '__main__':
    if len(sys.argv) < 4:
        exit("Usage: %s %s %s %s" % (sys.argv[0], 'nr_runs', 'conf_file', 'backup folder'))
    nun_runs = int(sys.argv[1])
    conf_file = sys.argv[2]
    backupdir = sys.argv[3]
    logger = logging.getLogger('probe')
    config = Configuration(conf_file)

    plugin_out_file = config.get_database_configuration()['pluginoutfile']
    logger.debug('Backup dir set at: %s' % backupdir)
    ff_launcher = FFLauncher(config)
    dbcli = DBClient(config)
    dbcli.create_tables()
    logger.debug('Starting nr_runs (%d)' % nun_runs)
    for i in range(nun_runs):
        stats = ff_launcher.browse_urls()
        if stats is None:
            logger.warning('Problem in session %d.. skipping' % i)
            continue
        if not os.path.exists(plugin_out_file):
            logger.error('Plugin outfile missing.')
            exit("Plugin outfile missing.")
        dbcli.load_to_db(stats)
        logger.debug('Ended browsing run n.%d' % i)
        new_fn = backupdir + '/' + plugin_out_file.split('/')[-1] + '.run%d' % i
        os.rename(plugin_out_file, new_fn)
        logger.debug('Saved plugin file for run n.%d: %s' % (i, new_fn))
        monitor = Monitor(config)
        monitor.run_active_measurement()
        logger.debug('Ended Active probing for run n.%d' % i)
        for tracefile in os.listdir('.'):
            if tracefile.endswith('.traceroute'):
                new_fn_trace = backupdir + '/' + tracefile + '.run%d' % i
                os.rename(tracefile, new_fn_trace)

    jc = JSONClient(config)
    jc.prepare_and_send()