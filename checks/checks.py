import pprint
import re
import sys
import utils
import logging
log = logging.getLogger('maas_migration')

_check_type_map = {
    'HTTP': 'remote.http',
    'HTTPS': 'remote.http',
    'PING': 'remote.ping',
    'SSH': 'remote.ssh',
    'DNS': 'remote.dns',
    'TCP': 'remote.tcp',
    'IO': 'agent.disk',
    'CPU': 'agent.cpu',
    'MEMORY': 'agent.memory',
    'PLUGIN': 'agent.plugin',
    'BANDWIDTH': 'agent.network',
}


class Checks(object):

    def __init__(self, cloudkick, rackspace, entity_map, monitoring_zones=None, auto=False, dry_run=False):
        self.cloudkick = cloudkick
        self.rackspace = rackspace
        self.entity_map = entity_map

        self.dry_run = dry_run
        self.auto = auto

        self.entities = rackspace.list_entities()
        self.nodes = cloudkick.nodes.read()['items']
        self.monitors = cloudkick.monitors.read()['items']

        # monitoring zones - generate a list of all available mzids and a human-readable label
        self.available_mzs = {}
        for mz in self.rackspace.list_monitoring_zones():
            self.available_mzs[mz.id] = '%s - %s %s' % (mz.id, mz.country_code, mz.label)

        # set (and validate) default monitoring zones if specified in the config
        self.mzs = monitoring_zones if monitoring_zones else []
        if self.mzs:
            if not all(mz in self.available_mzs.keys() for mz in self.mzs):
                log.error('Invalid monitoring zone config, ignoring...')
                self.mzs = []
        else:
            self.mzs = self._get_mzs()

    def _get_mzs(self, use_default=True):
        """
        if we don't have a default set of mzs yet, this prompts the user to choose
        """
        if self.mzs and use_default:
            return self.mzs

        # Validator for mz selection input
        def _validate_mzs(selection):
            mzs = re.findall(r'\w+', selection)
            valid = all([mz in self.available_mzs for mz in mzs])
            if mzs and valid:
                return True, mzs
            return False, 'Invalid Input'

        # Print readable mzs
        sys.stderr.write('Available Monitoring zones:\n')
        for mz in self.available_mzs.values():
            sys.stderr.write('%s\n' % (mz))

        # Collect input
        self.mzs = utils.get_input(msg='Choose monitoring zones (ex. "mzord,mzdfw")',
                                   null=False,
                                   validator=_validate_mzs)
        return self.mzs

    def _choose_ip(self, entity):
        """
        Return the primary ipv4 addr always, it's how Cloudkick works
        """
        for addr in entity.ip_addresses:
            if 'public0_v4' == addr[0]:
                return addr[1]

    def _populate_check(self, node, entity, check, monitor, new_check):

        # remote checks need to choose monitoring zones and a target IP
        if 'remote' in new_check['type']:
            # set up monitoring zones for the check
            new_check['monitoring_zones'] = self._get_mzs()
            # choose target
            new_check['target_hostname'] = self._choose_ip(entity)

        if new_check['type'] == 'remote.http':
            ck_details = check['details']

            rs_details = {}

            for attr in ['url', 'method', 'auth_user', 'auth_password', 'body']:
                if attr in ck_details:
                    rs_details[attr] = ck_details[attr]

            if not rs_details.get('method'):
                rs_details['method'] = 'GET'

            if check['type']['description'] == 'HTTPS':
                rs_details['ssl'] = True

            new_check['details'] = rs_details

        elif new_check['type'] == 'remote.ssh':
            new_check['details'] = {}
            new_check['details']['port'] = check['details']['port']

        elif new_check['type'] == 'remote.tcp':
            new_check['details'] = {}
            new_check['details']['port'] = check['details']['port']

            if 'use_ssl' in check['details']:
                new_check['details']['ssl'] = check['details']['use_ssl']

        elif new_check['type'] == 'remote.dns':
            new_check['details'] = {}
            new_check['details']['query'] = check['details']['dns_query']
            new_check['details']['record_type'] = check['details']['record_type']

    def _make_check(self, node, entity, check, monitor):
        # Basic check data
        new_check = {}
        new_check['label'] = '%s:%s' % (monitor['name'], check['type']['description'])
        new_check['type'] = _check_type_map[check['type']['description']]
        new_check['disabled'] = not check['is_enabled']
        new_check['metadata'] = {'ck_check_id': check['id']}

        # do check-specific stuff
        self._populate_check(node, entity, check, monitor, new_check)

        log.debug('Check:\n%s' % pprint.pformat(new_check))

        return new_check

    def _test_check(self, entity, new_check):
        try:
            responses = self.rackspace.test_check(entity, **new_check)
        except Exception as e:
            log.error('Check test failed - Exception:\n%s' % e)
            return False

        # if the check test failed we want to log.info it, otherwise it's safe to ignore and we log.debug
        valid = False not in [r['available'] for r in responses]
        log_fun = log.debug if valid else log.info
        log_fun('Check test %s!' % ('passed' if valid else 'failed'))
        log_fun('Results:\n%s' % (pprint.pformat(responses)))
        return valid

    def _get_or_create_check(self, node, entity, monitor, ck_check, rs_check=None):

        new_check = self._make_check(node, entity, ck_check, monitor)

        if rs_check and \
           new_check.get('details', {}) == rs_check.details and \
           new_check.get('target_hostname', None) == getattr(rs_check, 'target_hostname', None) and \
           new_check['type'] == rs_check.type and \
           new_check.get('monitoring_zones', None) == getattr(rs_check, 'monitoring_zones', None):
            return rs_check, 'Matched'

        success = self._test_check(entity, new_check)
        if not success:
            if utils.get_input('Check test failed - save anyway?', options=['y', 'n'], default='n') != 'y':
                return None, 'Skipped'
            else:
                success = True

        if success and self.auto or utils.get_input('Save this check?', options=['y', 'n'], default='y') == 'y':
            if rs_check:
                msg = 'Updated'
                new_check = self.rackspace.update_check(rs_check, new_check)
            else:
                msg = 'Created'
                new_check = self.rackspace.create_check(entity, **new_check)
            return new_check, msg
        return None, 'Skipped'

    def sync_checks(self):
        log.info('\nChecks')
        log.info('------\n')

        rv = []
        for node, entity in self.entity_map:

            log.info('Syncing checks for node %s\n' % utils.node_to_str(node))

            # CK checks
            ck_checks = self.cloudkick.checks.read(node_ids=node['id'])
            if ck_checks:
                ck_checks = ck_checks.get('items')
            else:
                log.info('No checks found for node %s' % utils.node_to_str(node))
                continue

            for ck_check in ck_checks:

                # get monitor that owns this check
                monitor = None
                for m in self.monitors:
                    if m['id'] == ck_check['monitor_id']:
                        monitor = m
                        break

                log.info('Cloudkick Check %s (%s:%s)' % (ck_check['id'], monitor.get('name'), ck_check['type']['description']))

                # is this a portable check type?
                check_type = ck_check['type']['description']
                if check_type not in _check_type_map.keys():
                    log.info('Check type "%s" not supported\n' % check_type)
                    continue

                # find previously migrated checks
                rs_check = None
                for c in self.rackspace.list_checks(entity):
                    if c.extra.get('ck_check_id') == ck_check['id']:
                        rs_check = c
                        break

                check, msg = self._get_or_create_check(node, entity, monitor, ck_check, rs_check)
                if check:
                    log.info('%s Rackspace Check %s' % (msg, check.id))
                    rv.append((node, entity, ck_check, check, monitor))
                else:
                    log.info('%s' % msg)
                log.info('')
        return rv
