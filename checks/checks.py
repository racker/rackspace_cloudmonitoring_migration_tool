import pprint

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
        self.mzs = self.rackspace.list_monitoring_zones()
        self.available_mzs = {}
        for mz in self.mzs:
            self.available_mzs[mz.id] = '%s - %s %s' % (mz.id, mz.country_code, mz.label)

        # set default monitoring zones if applicable, otherwise use all monitoring zones
        self.default_mzs = {}
        if monitoring_zones:
            for mz in monitoring_zones:
                if mz in self.available_mzs:
                    self.default_mzs[mz] = self.available_mzs[mz]
                else:
                    print 'Invalid monitoring zone %s' % mz
        else:
            self.default_mzs = self.available_mzs

    def _get_node_str(self, node):
        return '%s (%s) ips:%s' % (node.get('name'), node.get('id'), ','.join(node.get('public_ips', []) + node.get('private_ips', [])))

    def _get_entity_str(self, entity):
        return '%s (%s) ips:%s' % (entity.label, entity.id, ','.join([ip for _, ip in entity.ip_addresses]))

    def _populate_check(self, node, entity, check, monitor, new_check):

        # remote checks need to choose monitoring zones and a target IP
        if 'remote' in new_check['type']:
            # set up monitoring zones for the check
            new_check['monitoring_zones'] = [mz_id for mz_id, _ in self._choose_mzs(default=self.default_mzs).items()]
            # choose target
            new_check['target_hostname'] = self._choose_ip(entity)

        if new_check['type'] == 'remote.http':
            ck_details = check['details']

            rs_details = {}

            for attr in ['url', 'method', 'auth_user', 'auth_password', 'body']:
                if attr in ck_details:
                    rs_details[attr] = ck_details[attr]

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

        print 'Check:\n%s' % (pprint.pformat(new_check))

        return new_check

    def _choose_ip(self, entity):
        print 'Available Targets:'
        available_ips = []
        count = 0
        for addr in entity.ip_addresses:
            if 'private' not in addr[0]:
                available_ips.append(addr[1])
                print '%s - %s [%s]' % (addr[0], addr[1], count)
                count += 1

        target = None
        while not target:
            choice = 0 if self.auto else (raw_input('Choose Target (default 0): ') or 0)
            try:
                choice = int(choice)
            except ValueError:
                print 'Invalid Choice'
                continue

            if len(available_ips) < choice + 1:
                print 'Invalid Choice'
                continue

            target = available_ips[choice]
            print 'Chose %s - %s' % (choice, target)
        return target

    def _choose_mzs(self, default=None):
        if default:
            print 'Chosen default zones:'
            print '\n'.join(default.values())
            if self.auto or raw_input('Edit monitoring zones? [y/n] (default n): ') != 'y':
                return default

        default = self.available_mzs

        print 'Available monitoring zones:'
        print '\n'.join(self.available_mzs.values())

        while True:
            chosen_mzs = {}

            selection = raw_input('Enter choice (default is %s): ' % (','.join(default.keys() if default else ','.join(self.available_mzs.keys()))))

            if not selection:
                chosen_mzs = default
            else:
                for mz in selection.strip().split(','):
                    if mz in self.available_mzs:
                        chosen_mzs[mz] = self.available_mzs[mz]

            if not chosen_mzs:
                print 'No monitoring zones chosen.'
                continue

            print 'Chosen monitoring zones:'
            for mz_id, mz_label in chosen_mzs.items():
                print '%s' % (mz_label)

            correct = raw_input('Is this correct? [y/n]: ') == 'y'
            if correct:
                return chosen_mzs

    def _test_check(self, entity, new_check):
        try:
            responses = self.rackspace.test_check(entity, **new_check)
        except Exception as e:
            print 'Check test failed!'
            print 'Exception: %s' % e
            return False
        print pprint.pformat(responses)
        return False not in [r['available'] for r in responses]

    def _get_or_create_check(self, node, entity, check, monitor, old_checks):
        # find any previously existing checks
        old_check = None
        for c in old_checks:
            if c.extra.get('ck_check_id') == check['id']:
                old_check = c
                break

        new_check = self._make_check(node, entity, check, monitor)

        if old_check and \
           new_check.get('details', {}) == old_check.details and \
           new_check['target_hostname'] == old_check.target_hostname and \
           new_check['type'] == old_check.type and \
           new_check['monitoring_zones'] == old_check.monitoring_zones:
            print 'Check is up to date'
            return old_check

        if self.auto or raw_input('Do you want to test this check? [y/n]: ') == 'y':
            success = self._test_check(entity, new_check)
            if not success:
                if raw_input('Check Failed! Save check anyway? [y/n]: ') != 'y':
                    return None

        if self.auto or raw_input('Save this check? [y/n]') == 'y':
            if old_check:
                new_check = self.rackspace.update_check(old_check, new_check)
            else:
                new_check = self.rackspace.create_check(entity, **new_check)
            return new_check
        return None

    def sync_checks(self):
        # first, we need to know
        print '\nChecks'
        print '------\n'

        # We haven't set any default monitoring zones yet, so prompt the user here
        if self.default_mzs == self.available_mzs:
            print 'Choose default set of monitoring zones to poll from: '
            print '(You can change this on a per-check basis later)'
            self.default_mzs = self._choose_mzs()

        rv = []
        for node, entity in self.entity_map:
            print 'Syncing checks for node %s' % self._get_node_str(node)
            checks = self.cloudkick.checks.read(node_ids=node['id'])
            if checks:
                checks = checks.get('items')
            else:
                print 'No checks found for node %s' % self._get_node_str(node)
                continue

            old_checks = self.rackspace.list_checks(entity)
            for check in checks:
                if check['type']['description'] not in _check_type_map.keys():
                    continue
                for monitor in self.monitors:
                    if monitor['id'] == check['monitor_id']:
                        new_check = self._get_or_create_check(node, entity, check, monitor, old_checks)
                        if new_check:
                            rv.append((node, entity, check, new_check, monitor))
        return rv
