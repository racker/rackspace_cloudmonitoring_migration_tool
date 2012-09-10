import pprint
import re


class Entities(object):

    def __init__(self, cloudkick, rackspace, auto=False, dry_run=False):
        self.cloudkick = cloudkick
        self.rackspace = rackspace

        self.dry_run = dry_run
        self.auto = auto

        self.entities = rackspace.list_entities()
        self.agent_ids = dict([(e.id, e.agent_id) for e in self.entities])  # This sucks, but it works.
        self.nodes = cloudkick.nodes.read()['items']

    def _get_node_str(self, node):
        return '%s (%s) ips:%s' % (node.get('name'), node.get('id'), ','.join(node.get('public_ips', []) + node.get('private_ips', [])))

    def _get_entity_str(self, entity):
        return '%s (%s) ips:%s' % (entity.label, entity.id, ','.join([ip for _, ip in entity.ip_addresses]))

    def _get_agent_id(self, node, entity_id=None):

        if self.auto:
            return node['name']
        else:
            print 'Node %s' % self._get_node_str(node)
            print 'An agent_id is required to connect an agent to this entity.'
            print 'You will put this id in the rackspace_monitoring.conf file'
            print 'Would you like to specify an agent_id? [y/n] (default: n)',
            if raw_input() == 'y':
                while True:
                    result = raw_input('Choose an agent_id for this node: ')
                    if result and re.match('.*\s.*', result):
                        print 'Invalid Choice - must be null or contain no whitespace'
                    elif result and result in self.agent_ids.values() and result != self.agent_ids.get(entity_id):
                        print 'Invalid Choice - Colliding agent id with entity "%s"' % entity_id
                    else:
                        return result

    def _make_entity(self, node, entity_id=None):
        label = node.get('name')
        metadata = {'ck_node_id': node.get('id')}

        # add ips to the entity in a semi-consistent way
        primary_ip = node.get('ipaddress')
        public_ips = [ip for ip in node.get('public_ips') if ip != primary_ip]
        public_ips.sort()
        private_ips = node.get('private_ips')
        private_ips.sort()
        ips = {'public0_v4': primary_ip}
        for i, ip in enumerate(public_ips):
            key = 'public%s_v4' % (i + 1)
            ips[key] = ip
        for i, ip in enumerate(private_ips):
            key = 'private%s_v4' % (i)
            ips[key] = ip

        new_entity = {'label': label,
                      'ip_addresses': ips,
                      'metadata': metadata}

        agent_id = self._get_agent_id(node, entity_id)
        if agent_id:  # explicit empty string means something
            new_entity['agent_id'] = agent_id

        return new_entity

    def _update_entity_from_node(self, entity, node):
        new_entity = self._make_entity(node, entity_id=entity.id)

        new_entity.pop('label')  # leave existing label

        # check for matching IPs
        entity_ips = dict(entity.ip_addresses)
        if new_entity['ip_addresses'] == entity_ips:
            new_entity.pop('ip_addresses')

        if entity.extra.get('ck_node_id') == node['id']:
            new_entity.pop('metadata')

        if new_entity.get('agent_id') and entity.agent_id == new_entity.get('agent_id'):
            new_entity.pop('agent_id')

        if new_entity:
            print 'Updated entity %s' % (entity.id)
            print pprint.pformat(new_entity)
            if self.auto or raw_input('Update entity? [y/n]') == 'y':
                entity = self.rackspace.update_entity(entity, new_entity)
                return entity
        else:
            return entity

        return None

    def _create_entity_from_node(self, node):
        # if we get this far, we need to create an entity
        new_entity = self._make_entity(node)
        new_entity['extra'] = new_entity.pop('metadata')  # feels bad
        print 'New Entity:'
        print pprint.pformat(new_entity)
        if self.auto or raw_input('Create new entity? [y/n]') == 'y':
            entity = self.rackspace.create_entity(**new_entity)
            return entity

        return None

    def _get_or_create_entity_from_node(self, node):
        """
        There are 2 ways for us to match entities to CK nodes:
        1) entity metadata - nodes created via this script will put the ck node id in the entity metadata
        2) ip address - we will return the first entity with a matching public ip address (Which will catch entities
                        that have been pre-created other ways. (For example: rackspace cloud nodes))

        If neither of these methods work, we will create a new entity.
        """
        for entity in self.entities:

            # check in the entity metadata for ck_node_id first
            node_id = entity.extra.get('ck_node_id')
            if node_id == node.get('id'):
                return self._update_entity_from_node(entity, node)

            # we attempt to match entities based on public IP
            entity_ips = [ip for _, ip in entity.ip_addresses]
            for ip in node.get('public_ips', []):
                if ip in entity_ips:
                    return self._update_entity_from_node(entity, node)

        # We weren't able to find a matching entity, so we need to create a new one
        return self._create_entity_from_node(node)

    def sync_entities(self):
        """
        adds or updates entities in rs from nodes in ck

        @param cloudkick: extern.cloudkick_api.Connection instance
        @param rackspace: extern.rackspace_monitoring.drivers.rackspace.RackspaceMonitoringDriver instance
        """
        print '\nEntities'
        print '------\n'

        pairs = []
        for node in self.nodes:
            entity = self._get_or_create_entity_from_node(node)
            if entity:
                pairs.append((node, entity))

        # print out a report, if applicable
        matched = []
        node_ids = []
        entity_ids = []
        for node, entity in pairs:
            matched.append('Node %s -> Entity %s' % (self._get_node_str(node), self._get_entity_str(entity)))
            node_ids.append(node['id'])
            entity_ids.append(entity.id)

        if matched:
            print 'Matched Entities:'
            print '\n'.join(matched)

        orphaned = []
        print 'Orphaned Nodes:'
        for node in self.nodes:
            if node['id'] not in node_ids:
                orphaned.append(self._get_node_str(node))
        if orphaned:
            print 'Orphaned Nodes:'
            print '\n'.join(orphaned)

        orphaned = []
        for entity in self.entities:
            if entity.id not in entity_ids:
                orphaned.append(self._get_entity_str(entity))
        if orphaned:
            print 'Orphaned Entities:'
            print '\n'.join(orphaned)

        return pairs
