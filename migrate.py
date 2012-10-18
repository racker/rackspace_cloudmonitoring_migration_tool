#!/usr/bin/env python
"""
migrate.py - migration tool that moves checks from Cloudkick to Rackspace Cloud Monitoring
"""
import os
import sys
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path = [SCRIPT_DIR, os.path.join(SCRIPT_DIR, "extern")] + sys.path

from optparse import OptionParser

from entities import EntityMigrator
from checks import CheckMigrator
from notifications import NotificationMigrator
from alarms import AlarmMigrator

from tests.runner import run_tests

import utils

import traceback
import logging
log = logging.getLogger('maas_migration')


class Migrator(object):

    ck_api = None
    rs_api = None

    _rs_entities_cache = None

    migrated_entities = None

    def __init__(self, ck_api, rs_api, config, options):
        self.config = config
        self.options = options
        self.ck_api = ck_api
        self.rs_api = rs_api

        self.migrated_entities = []

    def _print_report(self):
        log.info('DONE')

    def get_rs_entities(self):
        if not self._rs_entities_cache:
            self._rs_entities_cache = self.rs_api.list_entities()
        return self._rs_entities_cache

    def migrate(self):
        e = EntityMigrator(self)
        e.migrate()
        c = CheckMigrator(self)
        c.migrate()
        n = NotificationMigrator(self)
        n.migrate()
        a = AlarmMigrator(self)
        a.migrate()
        self._print_report()


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
    m = Migrator(ck, rs, config, options)
    m.migrate()


def _setup(options, args):

    # setup, read config, init APIs
    utils.setup_logging('DEBUG')

    if args[0] == 'test':
        run_tests('%s/tests' % SCRIPT_DIR)
    else:
        config = utils.get_config(options.config) if options.config else {}
        utils.setup_ssl(options.ca_certs_path or config.get('ca_certs_path'))
        ck = utils.setup_ck(config.get('cloudkick_oauth_key'), config.get('cloudkick_oauth_secret'))
        rs = utils.setup_rs(config.get('rackspace_username'), config.get('rackspace_apikey'))

        # do work
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
    usage = 'usage: %prog [options] migrate/clean/shell/test'
    parser = OptionParser(usage=usage)
    parser.add_option("-c", "--config", dest="config", help="path to config file", metavar="FILE")
    parser.add_option("--dry-run", dest="dry_run", help="don't commit anything")
    parser.add_option("--ca-certs-path", action="store", dest="ca_certs_path", help="path to cacert bundle for ssl verification", metavar="FILE")
    parser.add_option("-o", "--output", dest="output", help="path to logfile", metavar="FILE")
    parser.add_option("-a", "--auto", action="store_true", dest="auto", default=False, help="don't prompt for anything")
    parser.add_option("--no-test", action="store_true", dest="no_test", default=False, help="Do *NOT* test checks and alarms before they are created")

    (options, args) = parser.parse_args()
    if not args or args[0] not in ['shell', 'clean', 'migrate', 'test']:
        parser.print_help()
        sys.exit()

    try:
        _setup(options, args)
    except Exception as e:
        type, value, tb = sys.exc_info()
        traceback.print_exc()
        import pdb
        pdb.post_mortem(tb)
