#!/usr/bin/env python
"""
migrate.py - migration tool that moves checks from Cloudkick to Rackspace Cloud Monitoring
"""
import os
import sys
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path = [SCRIPT_DIR, os.path.join(SCRIPT_DIR, "extern")] + sys.path

from optparse import OptionParser

from entities import Entities
from checks import Checks
from notifications import Notifications
from alarms import Alarms

import utils

import traceback
import logging
log = logging.getLogger('maas_migration')


def _print_report(entities, check, plans, alarms):
    log.info('Done')


def _clean(args, options, config, rs, ck):
    do_clean = utils.get_input('Do you want to purge all MaaS data?', options=['y', 'n'], default='n') == 'y'
    if not do_clean:
        log.info('exiting...')
        sys.exit(0)

    for e in rs.list_entities():
        for a in rs.list_alarms(e):
            a.delete()
            log.info('deleted alarm: %s' % a.id)
        for c in rs.list_checks(e):
            c.delete()
            log.info('deleted check: %s' % c.id)
        try:
            e.delete()
            log.info('deleted entity: %s' % e.id)
        except Exception as ex:
            log.info('failed deleting entity %s: %s' % (e.id, ex))

    for n in rs.list_notifications():
        n.delete()
        log.info('deleted notification: %s' % n.id)
    for p in rs.list_notification_plans():
        try:
            p.delete()
            log.info('deleted notification plan: %s' % p.id)
        except Exception as ex:
            log.info('failed deleting notification plan %s: %s' % (p.id, ex))


def _migrate(args, options, config, rs, ck):
    e = Entities(ck, rs, auto=options.auto, dry_run=options.dry_run)
    entities = e.sync_entities()
    c = Checks(ck, rs, entities, monitoring_zones=config.get('monitoring_zones', []), auto=options.auto, dry_run=options.dry_run)
    checks = c.sync_checks()
    n = Notifications(ck, rs, [c[4] for c in checks], auto=options.auto, dry_run=options.dry_run)
    plans = n.sync_notifications()
    a = Alarms(ck, rs, checks, plans, consistency_level=config.get('alarm_consistency_level', 'ALL'), auto=options.auto, dry_run=options.dry_run)
    alarms = a.sync_alarms()
    _print_report(entities, checks, plans, alarms)


def _setup(options, args):

    # setup logger
    utils.setup_logging('INFO' if options.quiet else 'DEBUG', options.output)

    # read config file
    config = utils.get_config(options.config) if options.config else {}

    # setup ssl
    utils.setup_ssl(options.ca_certs_path or config.get('ca_certs_path'))

    # init cloudkick api lib
    ck = utils.setup_ck(config.get('cloudkick_oauth_key'), config.get('cloudkick_oauth_secret'))

    # init rackspace api lib
    rs = utils.setup_rs(config.get('rackspace_username'), config.get('rackspace_apikey'))

    # do work
    args = args
    if args[0] == 'shell':
        try:
            from IPython import embed
            embed()
        except ImportError:
            import code
            code.interact(local=locals())
    elif args[0] == 'clean':
        _clean(args, options, config, rs, ck)
    elif args[0] == 'migrate':
        _migrate(args, options, config, rs, ck)
    else:
        parser.print_usage()

if __name__ == "__main__":
    usage = 'usage: %prog [options] migrate/purge/shell'
    parser = OptionParser(usage=usage)
    parser.add_option("-c", "--config", dest="config", help="path to config file", metavar="FILE")
    parser.add_option("--dry-run", action="store_true", dest="dry_run", default=False, help="don't commit anything, just print the report")
    parser.add_option("--ca_certs_path", action="store", dest="ca_certs_path", default=os.path.join(SCRIPT_DIR, "cacert.pem"), help="path to cacert bundle for ssl verification", metavar="FILE")
    parser.add_option("-d", "--debug", action="store_true", dest="debug", default=False, help="debug mode (more logging, drop to debugger on exception")
    parser.add_option("-o", "--output", dest="output", help="path to logfile", metavar="FILE")
    parser.add_option("-a", "--auto", action="store_true", dest="auto", default=False, help="don't prompt for anything")
    parser.add_option("-q", "--quiet", action="store_true", dest="quiet", default=False, help="log minimal info")

    (options, args) = parser.parse_args()
    if not args or args[0] not in ['shell', 'clean', 'migrate']:
        parser.print_help()
        sys.exit()

    try:
        _setup(options, args)
    except Exception as e:
        type, value, tb = sys.exc_info()
        traceback.print_exc()
        import pdb
        pdb.post_mortem(tb)
