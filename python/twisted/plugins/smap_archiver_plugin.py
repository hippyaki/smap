"""
Copyright (c) 2011, 2012, Regents of the University of California
All rights reserved.
...
"""

"""
@author Stephen Dawson-Haggerty <stevedh@eecs.berkeley.edu>
"""

import os
import sys
from zope.interface import implementer

from twisted.python import usage, log
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker, MultiService
from twisted.application import internet
from twisted.internet import reactor, ssl
from twisted.enterprise import adbapi

# Attempt to import psycopg2, handle errors gracefully
try:
    import psycopg2.extras
except ImportError:
    log.msg("psycopg2 not installed. PostgreSQL-related features will be disabled.")
    psycopg2 = None


class Options(usage.Options):
    optParameters = [["port", "p", None, "Service port number"]]
    optFlags = [["subscribe", "s", "Subscribe to sources"],
                ["memdebug", "m", "Print memory debugging information"]]

    def parseArgs(self, conf):
        self['conf'] = conf


@implementer(IServiceMaker, IPlugin)
class ArchiverServiceMaker(object):
    tapname = "smap-archiver"
    description = "A sMAP archiver"
    options = Options

    def makeService(self, options):
        if options['conf']:
            try:
                settings.conf = settings.load(options['conf'])
            except Exception as e:
                log.err(f"Failed to load configuration file: {e}")
                sys.exit(1)

        # Ensure required keys exist in the config
        threadpool_size = settings.conf.get('threadpool size', 10)
        reactor.suggestThreadPoolSize(threadpool_size)

        if options['memdebug']:
            from twisted.internet import task
            import objgraph
            import gc

            def stats():
                print(gc.collect())
                print("")
                print('\n'.join(map(str, objgraph.most_common_types(limit=10))))

            task.LoopingCall(stats).start(2)

        # Database Connection
        if 'database' not in settings.conf:
            log.err("Database configuration missing in settings. Exiting.")
            sys.exit(1)

        db_conf = settings.conf['database']
        if not all(key in db_conf for key in ['module', 'host', 'db', 'user', 'password', 'port']):
            log.err("Incomplete database configuration. Exiting.")
            sys.exit(1)

        def connection_callback(conn):
            """ Configure PostgreSQL connection settings """
            if psycopg2:
                conn.set_client_encoding("UTF8")
                psycopg2.extras.register_hstore(conn)

        cp = adbapi.ConnectionPool(db_conf['module'],
                                   host=db_conf['host'],
                                   database=db_conf['db'],
                                   user=db_conf['user'],
                                   password=db_conf['password'],
                                   port=db_conf['port'],
                                   cp_min=5, cp_max=30,
                                   cp_reconnect=True,
                                   cp_openfun=connection_callback)

        # Subscription handling
        if options['subscribe']:
            subscribe(cp, settings)

        # Republishers setup
        http_repub = republisher.ReResource(cp)
        websocket_repub = republisher.WebSocketRepublishResource(cp)

        mongo_repub = None
        if settings.conf.get('mongo', {}).get('enabled', False):
            mongo_repub = republisher.MongoRepublisher(cp)

        pg_repub = None
        if db_conf.get('republish', False):
            log.msg("Enabling PostgreSQL republishing")
            pg_repub = republisher.PostgresEndpoint(cp)

        service = MultiService()
        for svc, scfg in settings.conf.get('server', {}).items():
            site = getSite(cp,
                           resources=scfg.get('resources', []),
                           http_repub=http_repub,
                           websocket_repub=websocket_repub,
                           mongo_repub=mongo_repub,
                           pg_repub=pg_repub)

            if not scfg.get('ssl'):
                service.addService(internet.TCPServer(scfg['port'], site, interface=scfg.get('interface', '')))
            else:
                service.addService(internet.SSLServer(scfg['port'], site,
                                                      SslServerContextFactory(scfg['ssl']),
                                                      interface=scfg.get('interface', '')))

        return service


# Safe imports of required smap modules
try:
    from smap.archiver import settings, republisher
    from smap.subscriber import subscribe
    from smap.ssl import SslServerContextFactory
    from smap.archiver.server import getSite
except ImportError as e:
    log.err(f"Failed to import smap modules: {e}")
else:
    serviceMaker = ArchiverServiceMaker()
