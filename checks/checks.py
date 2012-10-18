import pprint
import utils
import logging

from copy import copy

DEFAULT_MONITORING_ZONES = ['mzord', 'mzdfw', 'mzlon']


class UnsupportedCheckType(Exception):
    pass


class MigratedCheck(object):
    """
    CK Check --> RS Check

    To implement a new check - add the CK type -> RS type entry to
    _check_type_map.

    Optionally, implement a private function on this class that is the same name
    of the RS check type and do any check-specific stuff there. (see _remote_http())
    """

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

    ck_api = None
    rs_api = None

    ck_node = None
    rs_entity = None

    ck_check = None
    rs_check = None

    rs_notification_plan = None

    migrated_alarms = []

    _check_cache = None

    def __init__(self, migrated_entity, ck_check, monitoring_zones=None, rs_checks_cache=None):

        if ck_check.type not in self._check_type_map:
            raise UnsupportedCheckType('Check type %s is not supported' % (ck_check.type))

        self.migrated_entity = migrated_entity

        self.ck_api = migrated_entity.ck_api
        self.rs_api = migrated_entity.rs_api
        self.ck_node = migrated_entity.ck_node
        self.rs_entity = migrated_entity.rs_entity

        self.ck_check = ck_check
        self.monitoring_zones = monitoring_zones or DEFAULT_MONITORING_ZONES

        self._check_cache = {}
        self._populate_check()

        self.rs_check = self._find_check()

        self.alarms = []

        self._test_responses_cache = None

    def __str__(self):
        return pprint.pformat(self._check_cache)

    @property
    def type(self):
        return self._check_cache['type']

    def _populate_check(self):

        # Basic check data
        self._check_cache['label'] = self.ck_check.label
        self._check_cache['type'] = self._check_type_map[self.ck_check.type]
        self._check_cache['disabled'] = self.ck_check.disabled
        self._check_cache['metadata'] = {'ck_check_id': self.ck_check.id}

        # remote checks need to choose monitoring zones and a target IP
        if 'remote' in self.type:
            # set up monitoring zones for the check
            self._check_cache['monitoring_zones'] = self.monitoring_zones
            # target
            self._check_cache['target_hostname'] = self.ck_check.target_hostname

        # do check specific stuff
        f = getattr(self, '_%s' % (self.type.replace('.', '_')), None)
        if f:
            f()

    def _find_check(self):

        for c in self.migrated_entity.get_rs_checks():
            if c.extra.get('ck_check_id') == self.ck_check.id:
                return c
        return None

    def test(self):
        try:
            if self._test_responses_cache:
                responses = self._test_responses_cache
            else:
                responses = self.rs_api.test_check(self.rs_entity, **self._check_cache)
                self._test_responses_cache = responses
        except Exception as e:
            msg = 'Check test failed - Exception:\n%s' % (e)
            return False, msg, self._test_responses_cache

        valid = False not in [r['available'] for r in responses]
        msg = 'Check test %s!\n' % ('passed' if valid else 'failed')
        return valid, msg, responses

    def save(self, commit=True):
        if not self.rs_check:
            if commit:
                self.rs_check = self.rs_api.create_check(self.rs_entity, **self._check_cache)
            return 'Created', self._check_cache

        c = copy(self._check_cache)

        if c['metadata'].get('ck_node_id') == self.rs_check.extra.get('ck_node_id'):
            c.pop('metadata')

        for key in ['details', 'label', 'monitoring_zones', 'disabled', 'target_hostname', 'type']:
            if c.get(key) == getattr(self.rs_check, key, None):
                try:
                    c.pop(key)
                except KeyError:
                    pass

        if c:
            if commit:
                self.rs_check = self.rs_api.update_check(self.rs_check, c)
            return 'Updated', c

        return 'Unchanged', None

    ########################
    # Check Specific Stuff #
    ########################
    def _remote_http(self):
        ck_details = self.ck_check.details
        rs_details = {}

        for attr in ['url', 'method', 'auth_user', 'auth_password', 'body']:
            if attr in ck_details:
                rs_details[attr] = ck_details[attr]

        if not rs_details.get('method'):
            rs_details['method'] = 'GET'

        if self.ck_check.type == 'HTTPS':
            rs_details['ssl'] = True

        self._check_cache['details'] = rs_details

    def _remote_ssh(self):
        self._check_cache['details'] = {}
        self._check_cache['details']['port'] = self.ck_check.details['port']

    def _remote_tcp(self):
        self._check_cache['details'] = {}
        self._check_cache['details']['port'] = self.ck_check.details['port']
        if 'use_ssl' in self.ck_check.details:
            self._check_cache['details']['ssl'] = self.ck_check.details['use_ssl']

    def _remote_dns(self):
        self._check_cache['details'] = {}
        self._check_cache['details']['query'] = self.ck_check.details['dns_query']
        self._check_cache['details']['record_type'] = self.ck_check.details['record_type']

    def _agent_plugin(self):
        self._check_cache['details'] = {}
        self._check_cache['details']['file'] = self.ck_check.details['check']
        args = self.ck_check.details.get('args')
        if args:
            self._check_cache['details']['args'] = args.split(' ')


class CheckMigrator(object):

    def __init__(self, migrator, logger=None):
        self.logger = logger
        if not self.logger:
            self.logger = logging.getLogger('maas_migration')

        self.migrator = migrator
        self.ck_api = self.migrator.ck_api
        self.rs_api = self.migrator.rs_api

        self.monitoring_zones = self.migrator.config.get('monitoring_zones')

        self.no_test = self.migrator.options.no_test
        self.dry_run = self.migrator.options.dry_run
        self.auto = self.migrator.options.auto

    def _test(self, check):
        if self.no_test:
            return True

        result, msg, responses = check.test()

        self.logger.info(msg)
        self.logger.debug('Check Test Result:\n%s' % pprint.pformat(responses))
        if not result:
            if utils.get_input('Ignore this check?', options=['y', 'n'], default='y') == 'y':
                return False
        return True

    def migrate(self):
        self.logger.info('\nChecks')
        self.logger.info('------\n')

        for migrated_entity in self.migrator.migrated_entities:

            self.logger.info('Migrating checks for node %s\n' % migrated_entity.ck_node)

            rs_checks = self.rs_api.list_checks(migrated_entity.rs_entity)
            for ck_check in self.ck_api.list_checks(migrated_entity.ck_node):

                self.logger.info('Migrating Check %s' % (ck_check))

                try:
                    check = MigratedCheck(migrated_entity, ck_check, monitoring_zones=self.monitoring_zones, rs_checks_cache=rs_checks)
                except UnsupportedCheckType as e:
                    self.logger.info(e)
                    self.logger.info('')
                    continue

                action, result = check.save(commit=False)
                if action == 'Created':
                    if self._test(check):
                        self.logger.info('Creating new check:\n%s' % (pprint.pformat(result)))
                        if self.auto or utils.get_input('Create this check?', options=['y', 'n'], default='y') == 'y':
                            check.save()
                            migrated_entity.migrated_checks.append(check)
                elif action == 'Updated':
                    if self._test(check):
                        self.logger.info('Updating check %s - changes:\n%s' % (check.rs_check.id, pprint.pformat(result)))
                        if self.auto or utils.get_input('Update this check?', options=['y', 'n'], default='y') == 'y':
                            check.save()
                            migrated_entity.migrated_checks.append(check)
                else:
                    self.logger.info('No changes needed for check %s' % (check.rs_check.id))
                    migrated_entity.migrated_checks.append(check)

                self.logger.info('')
            self.logger.info('')
