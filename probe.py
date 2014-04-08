#!/usr/bin/python
import sys
import os
import shutil
import logging
import logging.config
from probe.Configuration import Configuration
from probe.FFLauncher import FFLauncher
from probe.PJSLauncher import PJSLauncher
from probe.DBClient import DBClient

logging.config.fileConfig('probe/logging.conf')

if __name__ == '__main__':
    if len(sys.argv) < 4:
        exit("Usage: %s %s %s %s" % (sys.argv[0], 'nr_runs', 'conf_file', 'backup folder'))
    nun_runs = int(sys.argv[1])
    conf_file = sys.argv[2]
    backupdir = sys.argv[3]
    logger = logging.getLogger('probe')
    config = Configuration(conf_file)
    browser = config.get_default_browser()['browser']
    logger.debug('Browser set as: %s' % browser)
    if browser == 'firefox':
	plugin_out_file = config.get_database_configuration()['pluginoutfile']
	launcher = FFLauncher(config)
    elif browser == 'phantomjs':
	plugin_out_file = config.get_database_configuration()['tstatfile']
	harfile = config.get_database_configuration()['harfile']
	launcher = PJSLauncher(config)
    else:
	logger.debug('Browser set as: %s - WRONG BROWSER !!' % browser)
	exit(0)
    
    logger.debug('Backup dir set at: %s' % backupdir)
    dbcli = DBClient(config)
    dbcli.create_tables()
    logger.debug('Starting nr_runs (%d)' % nun_runs)
    for i in range(nun_runs):       
	for line in open(launcher.browser_config['urlfile']):
	    stats = launcher.browse_url(line) 
	    if not os.path.exists(plugin_out_file):
                logger.error('Plugin outfile missing.')
                exit("Plugin outfile missing.")
            dbcli.load_to_db(stats, browser)
            logger.debug('Ended browsing run n.%d' % i)
	    new_fn = backupdir + '/' + plugin_out_file.split('/')[-1] + '.' + line.strip() +'_run%d' % i        
	    shutil.copyfile(plugin_out_file, new_fn)	# Quick and dirty not to delete Tstat log
	    open(plugin_out_file, 'w').close()	
	    if browser == 'phantomjs':
	        new_har = backupdir + '/' + harfile.split('/')[-1] + '.' + line.strip() +'_run%d' % i
	        os.rename(harfile, new_har)
            logger.debug('Saved plugin file for run n.%d: %s' % (i,new_fn))
        
