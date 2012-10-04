import sys
import os
import json
import getpass

import logging
log = logging.getLogger('maas_migration')


def setup_logging(loglevel, outfile=None):
    """
    configure logging
    """
    logging.basicConfig(format='%(message)s', level=loglevel)

    # optionally log to a file
    if outfile:
        hdlr = logging.FileHandler(outfile)
        log.addHandler(hdlr)


def get_input(msg=None, options=None, default=None, null=False, validator=None, hidden=False):
    """
    get input from user, but print prompt to stderr so it's not nabbed by output redirection.
    """

    # ensure options is iterable
    try:
        iter(options)
    except TypeError:
        options = []

    # build prompt string
    prompt = msg if msg else 'Input'
    if options:
        prompt += ' [%s]' % '/'.join([opt if opt != default else '[%s]' % opt for opt in options])
    if default and not options:
        prompt += ' [%s]' % default
    if msg or default or options:
        prompt += ': '

    while True:

        sys.stderr.write(prompt)

        try:
            if hidden:
                val = getpass.getpass()
            else:
                val = raw_input()
        except (KeyboardInterrupt):
            sys.stderr.write('\n')
            val = ''
            continue
        except (EOFError):
            sys.stderr.write('\n')
            sys.exit()

        # if input is empty, use the default
        if not val and default:
            return default

        # if we have a custom validator, validate input passes validator callback
        if validator:
            valid, result = validator(val)
            if valid:
                return result
            else:
                sys.stderr.write('%s\n' % result)
                continue

        # validate input is allowed
        if options and val not in options:
            sys.stderr.write('Input must be one of: %s\n' % ', '.join(options))
            val = ''
            continue

        # validate input is not null
        if not null and not val:
            sys.stderr.write('Input required\n')
            val = ''
            continue

        return val


def setup_rs(rs_username=None, rs_api_key=None):
    """
    set up rackspace_monitoring, prompt for key/secret if not configured
    """
    from rackspace_monitoring.providers import get_driver
    from rackspace_monitoring.types import Provider

    if not rs_username:
        rs_username = get_input("Rackspace Username: ")
    if not rs_api_key:
        rs_api_key = get_input("Rackspace API Key: ", hidden=True)

    try:
        driver = get_driver(Provider.RACKSPACE)(rs_username, rs_api_key)
        len(driver.list_entities())
        log.debug('Rackspace Cloud Monitoring API: ok')
        return driver
    except Exception as e:
        log.error('Rackspace Cloud Monitoring API: failed - %s' % e,)
        sys.exit(1)


def setup_ck(ck_oauth_key=None, ck_oauth_secret=None):
    """
    set up cloudkick-py, prompt for key/secret if not configured
    """
    from cloudkick_api import Connection

    if not ck_oauth_key:
        ck_oauth_key = get_input("Cloudkick OAuth Key: ")
    if not ck_oauth_secret:
        ck_oauth_secret = get_input("Cloudkick OAuth Secret: ", hidden=True)

    try:
        conn = Connection(oauth_key=str(ck_oauth_key), oauth_secret=str(ck_oauth_secret))
        len(conn.nodes.read()["items"])
        log.debug('Cloudkick API: ok')
        return conn
    except Exception as e:
        log.error('Cloudkick API: failed - %s' % e)
        sys.exit(1)


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
        log.error("Failed to read config file: %s" % e)
        sys.exit(1)
    except ValueError as e:
        log.error("failed to parse config: %s" % e)
        sys.exit(1)

    return config


def setup_ssl(path=None):
    """
    Sets up and checks libcloud.security.CA_CERTS_PATH, appending any pre-configured paths
    """
    import libcloud.security

    if path:
        libcloud.security.CA_CERTS_PATH.append(path)

    # if no CA bundles are found we need to do something
    if not any([os.path.exists(path) for path in libcloud.security.CA_CERTS_PATH]):
        log.debug("SSL CA bundle not found.")
        log.debug("You can find an updated bundle here: http://curl.haxx.se/ca/cacert.pem")
        log.debug("You can specify where to look with 'ca_cert_path' in the config.")
        log.debug("Would you like to continue without verifying SSL certs? ",)
        if get_input('Would you like to continue without verifying SSL certs?', options=['y', 'n'], default='n') == 'y':
            libcloud.security.VERIFY_SSL_CERT = False
            return
        else:
            sys.exit(1)


# pass a RS notification from the API and get out a nicely formatted string
def notification_to_str(notification):
    return '%s (%s) %s:%s' % (notification.label, notification.id, notification.type, notification.details)


# pass a CK node dict from the API and get out a nicely formatted string
def node_to_str(node):
    if not node:
        return 'None'
    return '%s (%s) ips:%s' % (node.get('name'), node.get('id'), ','.join(node.get('public_ips', []) + node.get('private_ips', [])))


# pass in a RS entity from the API and get out a nicely formatted string
def entity_to_str(entity):
    if not entity:
        return 'None'
    return '%s (%s) agent_id:%s ips:%s' % (entity.label, entity.id, entity.agent_id, ','.join([ip for _, ip in entity.ip_addresses]))
