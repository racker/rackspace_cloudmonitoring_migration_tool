"""
Loose wrapper that provides the same (read-only) interface and objects
as the Rackspace Cloud Monitoring libcloud driver
"""

import sys

from base import Connection


class Notification(object):
    name = None
    address = None
    type = None

    def __init__(self, type, name, address):
        self.name = name
        self.type = type
        self.address = address

    def __eq__(self, other):
        if hasattr(other, 'address') and other.address == self.address:
            return True
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self.address


class Monitor(object):
    monitor = None
    check = None
    address = None

    _type_map = {
        'webhook': 4,
        'email': 1
    }

    def __init__(self, ck_monitor):
        self.id = ck_monitor['id']
        self.name = ck_monitor['name']
        self.notification_receivers = ck_monitor['notification_receivers']

    def get_notifications(self):
        """
        Email only
        """
        notifications = []
        for n in self.notification_receivers:
            if n['type']['code'] == 1:
                notifications.append(Notification('email', n['name'], n['details']['email_address']))
        return notifications


class Check(object):
    id = None
    monitor = None
    label = None
    type = None
    details = None
    node_id = None
    disabled = None

    def __init__(self, node, ck_check, ck_monitor):

        self.id = ck_check['id']
        self.monitor = Monitor(ck_monitor)
        self.type = ck_check['type']['description']
        self.label = '%s:%s' % (self.monitor.name, self.type)
        self.details = ck_check['details']
        self.node = node
        self.disabled = not ck_check['is_enabled']
        self.target_hostname = self.node.primary_ip

    def __str__(self):
        return "<Check: id=%s label=%s ip=%s>" % (self.id, self.label, self.node.primary_ip)


class Node(object):

    id = None
    label = None
    ip_addresses = None
    agent_id = None
    extra = None

    def __init__(self, ck_node):
        self.id = ck_node['id']
        self.label = ck_node['name']
        self.agent_id = ck_node['id']
        self.ip_addresses = self._get_ip_addresses(ck_node)
        self.extra = {}

    def __str__(self):
        return "<Node: id=%s label=%s ip=%s>" % (self.id, self.label, self.ip_addresses.get('public0_v4'))

    @property
    def primary_ip(self):
        """
        Return primary public always, it's how CK works
        """
        return self.ip_addresses.get('public0_v4')

    def _get_ip_addresses(self, ck_node):
        """
        Translate CK ip list ()
        """
        primary_ip = ck_node.get('ipaddress')
        public_ips = [ip for ip in ck_node.get('public_ips') if ip != primary_ip]
        public_ips.sort()
        private_ips = ck_node.get('private_ips')
        private_ips.sort()
        ips = {'public0_v4': primary_ip}
        for i, ip in enumerate(public_ips):
            key = 'public%s_v4' % (i + 1)
            ips[key] = ip
        for i, ip in enumerate(private_ips):
            key = 'private%s_v4' % (i)
            ips[key] = ip
        return ips


class CloudkickApi(object):
    conn = None

    def __init__(self, oauth_key, oauth_secret):

        try:
            self.conn = Connection(oauth_key=str(oauth_key), oauth_secret=str(oauth_secret))
        except Exception as e:
            sys.stderr.write('Failed to initialize Cloudkick API.\n')
            sys.stderr.write('Exception: %s' % (e))
            sys.exit(1)

    def list_checks(self, node, use_cache=False):

        checks = []

        ck_monitors = self.conn.monitors.read()
        if ck_monitors:
            ck_monitors = ck_monitors['items']
        else:
            ck_monitors = []

        ck_checks = self.conn.checks.read(node_ids=node.id)
        if ck_checks:
            ck_checks = ck_checks['items']
        else:
            ck_checks = []

        for ck_check in ck_checks:

            # look up this check's monitor
            monitor = None
            for ck_monitor in ck_monitors:
                if ck_monitor['id'] == ck_check['monitor_id']:
                    monitor = ck_monitor
                    break

            checks.append(Check(node, ck_check, monitor))

        return checks

    def list_nodes(self, use_cache=False):
        nodes = []
        for node in self.conn.nodes.read()['items']:
            nodes.append(Node(node))
        return nodes
