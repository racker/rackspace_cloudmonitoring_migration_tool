#!/usr/bin/env python
"""
migrate.py - migration tool that moves checks from Cloudkick to Rackspace Cloud Monitoring
"""
import os
import sys

from optparse import OptionParser
import getpass
import json

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

sys.path = [os.path.join(SCRIPT_DIR, "extern")] + sys.path
import libcloud.security

from cloudkick_api import Connection

from rackspace_monitoring.providers import get_driver
from rackspace_monitoring.types import Provider

from entities import Entities
from checks import Checks
from notifications import Notifications
from alarms import Alarms


def get_config(config_file):
    """
    Try and read the json config file.

    @param config_file: path to valid json config file
    """
    config = {}
    if not config_file:
        return config
    try:
        f = open(config_file)
        config = json.loads(f.read())
    except IOError as e:
        print "failed to read config file: %s" % e
        sys.exit(1)
    except ValueError as e:
        print "failed to parse config: %s" % e
        sys.exit(1)

    return config


def setup_ssl(config):
    """
    Sets up and checks libcloud.security.CA_CERTS_PATH, appending any pre-configured paths

    @param config: dict parsed from json config file
    """
    libcloud.security.CA_CERTS_PATH.append(str(config.get('ca_certs_path')))

    # if no CA bundles are found we need to do something
    if not any([os.path.exists(path) for path in libcloud.security.CA_CERTS_PATH]):
        print "SSL CA bundle not found."
        print "You can find an updated bundle here: http://curl.haxx.se/ca/cacert.pem"
        print "You can specify where to look with 'ca_cert_path' in the config."
        print "Would you like to continue without verifying SSL certs? ",
        if raw_input('[y/n] ').strip() == 'y':
            libcloud.security.VERIFY_SSL_CERT = False
            return
        else:
            sys.exit(1)


def setup_ck(config):
    """
    set up cloudkick-py, prompt for key/secret if not configured

    @param config: dict parsed from json config file
    """
    conn = None
    ck_oauth_key = config.get('cloudkick_oauth_key')
    ck_oauth_secret = config.get('cloudkick_oauth_secret')

    if not ck_oauth_key:
        ck_oauth_key = raw_input("Cloudkick OAuth Key: ")
    if not ck_oauth_secret:
        ck_oauth_secret = getpass.getpass("Cloudkick OAuth Secret: ")

    try:
        print 'Cloudkick API:',
        conn = Connection(oauth_key=str(ck_oauth_key), oauth_secret=str(ck_oauth_secret))
        len(conn.nodes.read()["items"])
        print 'ok'
    except Exception as e:
        print 'failed - %s' % e
        sys.exit(1)

    return conn


def setup_rs(config):
    """
    set up rackspace_monitoring, prompt for key/secret if not configured

    @param config: dict parsed from json config file
    """
    driver = None
    rs_username = config.get('rackspace_username')
    rs_api_key = config.get('rackspace_apikey')

    if not rs_username:
        rs_username = raw_input("Rackspace Username: ")
    if not rs_api_key:
        rs_api_key = getpass.getpass("Rackspace API Key: ")
    try:
        print 'Rackspace Cloud Monitoring:',
        driver = get_driver(Provider.RACKSPACE)(rs_username, rs_api_key)
        len(driver.list_entities())
        print 'ok'
    except Exception as e:
        print 'failed - %s' % e
        sys.exit(1)

    return driver


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-c", "--config", dest="config", default=os.path.join(SCRIPT_DIR, "config.json"), help="path to config file", metavar="FILE")
    parser.add_option("--dry-run", action="store_true", dest="dry_run", default=False, help="don't commit anything, just print the report")
    parser.add_option("--auto", action="store_true", dest="auto", default=False, help="don't prompt for anything")
    (options, args) = parser.parse_args()

    config = get_config(options.config)
    setup_ssl(config)
    ck = setup_ck(config)
    rs = setup_rs(config)

    if len(args) == 1 and args[0] == 'shell':
        try:
            import IPython
            IPython.embed()
        except ImportError:
            import code
            code.interact(local=locals())
    elif len(args) == 1 and args[0] == 'clean':
        if raw_input('Do you want to purge all MaaS data? [y/n] ') != 'y':
            print 'aborting'
            sys.exit(0)
        for e in rs.list_entities():
            for a in rs.list_alarms(e):
                print 'deleting alarm %s:' % a,
                a.delete()
                print 'ok'
            for c in rs.list_checks(e):
                print 'deleting check %s:' % c,
                c.delete()
                print 'ok'
            try:
                print 'deleting entity %s:' % e,
                e.delete()
                print 'ok'
            except Exception as e:
                print 'failed'
        for n in rs.list_notifications():
            print 'deleting notification %s:' % n,
            n.delete()
            print 'ok'
        for p in rs.list_notification_plans():
            print 'deleting notification plan %s:' % p,
            try:
                p.delete()
                print 'ok'
            except Exception as e:
                print 'failed'
    elif len(args) == 2 and args[0] == 'notifications':
        if args[1] == 'sync':
            monitors = ck.monitors.read()['items']
            n = Notifications(ck, rs, monitors, auto=options.auto, dry_run=options.dry_run)
            n.sync_notifications()
        elif args[1] == 'clean':
            print 'Clearing all notifications and plans'

            print 'Deleting notification plans'
            for p in rs.list_notification_plans():
                try:
                    print 'Deleting %s:' % p,
                    p.delete()
                    print 'Done'
                except Exception as e:
                    print 'Delete failed'

            print 'Deleting notifications'
            for n in rs.list_notifications():
                print 'Deleting %s: ' % n,
                n.delete()
                print 'Done'
    else:
        # synchronize entities
        e = Entities(ck, rs, auto=options.auto, dry_run=options.dry_run)
        entities = e.sync_entities()
        c = Checks(ck, rs, entities, monitoring_zones=config.get('monitoring_zones', []), auto=options.auto, dry_run=options.dry_run)
        checks = c.sync_checks()
        n = Notifications(ck, rs, [c[4] for c in checks], auto=options.auto, dry_run=options.dry_run)
        plans = n.sync_notifications()
        a = Alarms(ck, rs, checks, plans, consistency_level=config.get('alarm_consistency_level', 'ALL'), auto=options.auto, dry_run=options.dry_run)
        alarms = a.sync_alarms()
