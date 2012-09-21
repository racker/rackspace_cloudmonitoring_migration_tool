import pprint
import re

import utils
import logging
log = logging.getLogger('maas_migration')


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
        if not node:
            return 'None'
        return '%s (%s) ips:%s' % (node.get('name'), node.get('id'), ','.join(node.get('public_ips', []) + node.get('private_ips', [])))

    def _get_entity_str(self, entity):
        if not entity:
            return 'None'
        return '%s (%s) agent_id:%s ips:%s' % (entity.label, entity.id, entity.agent_id, ','.join([ip for _, ip in entity.ip_addresses]))

    def _get_agent_id(self, node, entity=None):

        def _check_id(agent_id):
            if not agent_id:
                return 'agent_id is null'

            # ensure agent_id has no whitespace
            if agent_id and re.match('.*\s.*', agent_id):
                return 'agent_id cannot contain whitespace'

            # ensure agent_id is not already in use
            for eid, aid in self.agent_ids.items():
                if aid == agent_id:
                    entity_id = entity.id if entity else False
                    if eid != entity_id:
                        return 'agent_id "%s" is already in use by another entity' % agent_id

            return True

        # use existing agent_id if available, the node name otherwise
        name = entity.agent_id if entity else node['name'].replace(' ', '_')
        result = _check_id(name)
        if result == True:
            return name

        return utils.get_input('Cannot automatically set agent_id for node "%s" -- %s.\nPlease choose a different agent_id' % (node['name'], result),
                               validator=_check_id)

    def _make_entity(self, node, entity=None):
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

        agent_id = self._get_agent_id(node, entity)
        if agent_id:
            new_entity['agent_id'] = agent_id

        return new_entity

    def _update_entity_from_node(self, entity, node):
        new_entity = self._make_entity(node, entity=entity)

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
            log.debug('Updated fields on entity %s:' % (entity.id))
            log.debug(pprint.pformat(new_entity))
            if self.auto or utils.get_input('Update entity?', options=['y', 'n'], default='y') == 'y':
                entity = self.rackspace.update_entity(entity, new_entity)
                if new_entity.get('agent_id'):
                    self.agent_ids[entity.id] = new_entity.get('agent_id')
                return 'Updated', entity
        else:
            log.debug('No update needed for entity %s' % (entity.id))
            return 'Matched', entity

        return False, None

    def _create_entity_from_node(self, node):
        # if we get this far, we need to create an entity
        new_entity = self._make_entity(node)
        new_entity['extra'] = new_entity.pop('metadata')  # feels bad
        log.debug('New Entity:')
        log.debug(pprint.pformat(new_entity))
        if self.auto or utils.get_input('Create new entity?', options=['y', 'n'], default='y') == 'y':
            entity = self.rackspace.create_entity(**new_entity)
            self.agent_ids[entity.id] = entity.agent_id
            return 'Created', entity

        return False, None

    def _get_or_create_entity_from_node(self, node):
        """
        There are 2 ways for us to match entities to CK nodes:
        1) entity metadata - nodes created via this script will put the ck node id in the entity metadata
        2) ip address - we will return the first entity with a matching public ip address (Which will catch entities
                        that have been pre-created other ways. (For example: rackspace cloud nodes))

        If neither of these methods work, we will create a new entity.
        """
        for entity in self.entities:

            match = None
            # check in the entity metadata for ck_node_id first
            node_id = entity.extra.get('ck_node_id')
            if node_id == node.get('id'):
                match = entity

            # we attempt to match entities based on public IP
            entity_ips = [ip for _, ip in entity.ip_addresses]
            for ip in node.get('public_ips', []):
                if ip in entity_ips:
                    match = entity

            if match:
                log.debug('Found matching entity: %s' % self._get_entity_str(entity))
                return self._update_entity_from_node(entity, node)

        # We weren't able to find a matching entity, so we need to create a new one
        log.debug('Creating new entity for node: %s' % self._get_node_str(node))
        return self._create_entity_from_node(node)

    def sync_entities(self):
        """
        adds or updates entities in rs from nodes in ck
        """
        log.info('\nEntities')
        log.info('------\n')

        pairs = []
        for node in self.nodes:
            log.info('Migrating node %s' % self._get_node_str(node))
            msg, entity = self._get_or_create_entity_from_node(node)
            if msg:
                log.info('%s entity %s\n' % (msg, self._get_entity_str(entity)))
                pairs.append((node, entity))
            else:
                log.info('No entity created for node %s\n' % self._get_node_str(node))

        # print out a report, if applicable
        if not utils.get_input('Would you like to print a full entity report?', options=['y', 'n'], default='y') == 'y':
            return pairs

        matched = []
        node_ids = []
        entity_ids = []
        for node, entity in pairs:
            matched.append('Node %s -> Entity %s' % (self._get_node_str(node), self._get_entity_str(entity)))
            node_ids.append(node['id'])
            entity_ids.append(entity.id)

        if matched:
            log.info('Node --> Entity:')
            log.info('%s\n' % '\n'.join(matched))

        orphaned = []
        for node in self.nodes:
            if node['id'] not in node_ids:
                orphaned.append(self._get_node_str(node))
        if orphaned:
            log.info('Orphaned Nodes:')
            log.info('%s' % '\n'.join(orphaned))

        orphaned = []
        for entity in self.entities:
            if entity.id not in entity_ids:
                orphaned.append(self._get_entity_str(entity))
        if orphaned:
            log.info('Orphaned Entities:')
            log.info('%s' % '\n'.join(orphaned))

        return pairs
