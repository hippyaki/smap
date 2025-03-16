"""
Copyright (c) 2011, 2012, Regents of the University of California
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions 
are met:

 - Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
 - Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the
   distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT 
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS 
FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL 
THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, 
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES 
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR 
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) 
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, 
STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED 
OF THE POSSIBILITY OF SUCH DAMAGE.
"""

"""
@author Stephen Dawson-Haggerty <stevedh@eecs.berkeley.edu>
"""

import sys
import os
from configobj import ConfigObj
from validate import Validator
from twisted.internet import reactor
from twisted.python import log


def setup_statsd(config):
    """ Setup statsd monitoring if configured """
    if 'statsd' not in config or not config['statsd'].get('host'):
        log.msg("StatsD not configured. Skipping setup.")
        return
    
    try:
        from txstatsd.client import TwistedStatsDClient, StatsDClientProtocol
        from txstatsd.metrics.metrics import Metrics

        global metrics
        statsd = TwistedStatsDClient(config['statsd']['host'],
                                     int(config['statsd']['port']))
        metrics = Metrics(connection=statsd,
                          namespace='smap-archiver.' + config['statsd'].get('prefix', 'default'))
        protocol = StatsDClientProtocol(statsd)
        reactor.listenUDP(0, protocol)
    except ImportError as e:
        log.err(f"Failed to import StatsD modules: {e}")


def import_rdb(settings):
    """ Import the readingdb module if configured """
    global rdb
    if 'readingdb' not in settings or 'module' not in settings['readingdb']:
        log.msg("ReadingDB module not configured. Skipping import.")
        return

    try:
        __import__(settings['readingdb']['module'])
        rdb = sys.modules[settings['readingdb']['module']]

        if 'host' in settings['readingdb'] and 'port' in settings['readingdb']:
            try:
                rdb.db_setup(settings['readingdb']['host'],
                             int(settings['readingdb']['port']))
            except AttributeError:
                pass
    except ImportError as e:
        log.err(f"Failed to import readingdb module: {e}")


def load(conffile):
    """ Load the configuration file """
    config_path = os.path.join(os.path.dirname(sys.modules[__name__].__file__), "settings.spec")
    config = ConfigObj(conffile, configspec=config_path, stringify=True, indent_type='  ')

    val = Validator()
    if not config.validate(val):
        log.err("Configuration validation failed.")
        return None

    # Import the readingdb module if configured
    import_rdb(config)

    # Setup StatsD if configured
    if 'statsd' in config and config['statsd'].get('host'):
        setup_statsd(config)

    return config


# Try to load the site configuration
conf = load('/etc/smap/archiver.ini')
if conf is None:
    log.err("Failed to load configuration. Exiting.")
    sys.exit(1)

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    log.msg("psycopg2 not installed. PostgreSQL features will be disabled.")
else:
    def connect(*args, **kwargs):
        conn = psycopg2.connect(*args, **kwargs)
        psycopg2.extras.register_hstore(conn)
        return conn
