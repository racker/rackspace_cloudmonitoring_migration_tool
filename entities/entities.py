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

    def _get_agent_id(self, node, entity=None):

        def _check_id(agent_id):
            if not agent_id:
                return False, 'agent_id is null'

            # ensure agent_id has no whitespace
            if agent_id and re.match('.*\s.*', agent_id):
                return False, 'agent_id cannot contain whitespace'

            # ensure agent_id is not already in use
            for eid, aid in self.agent_ids.items():
                if aid == agent_id:
                    entity_id = entity.id if entity else False
                    if eid != entity_id:
                        return False, 'agent_id "%s" is already in use by another entity' % agent_id

            return True, agent_id

        # use existing agent_id if available, the node name otherwise
        name = entity.agent_id if entity else node['name'].replace(' ', '_')
        result, msg = _check_id(name)
        if result == True:
            return msg

        return utils.get_input('Cannot automatically set agent_id for node "%s" -- %s.\nPlease choose a different agent_id' % (node['name'], msg),
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
                return self._update_entity_from_node(entity, node)

        # We weren't able to find a matching entity, so we need to create a new one
        log.debug('Creating new entity for node: %s' % utils.node_to_str(node))
        return self._create_entity_from_node(node)

    def sync_entities(self):
        """
        adds or updates entities in rs from nodes in ck
        """
        log.info('\nEntities')
        log.info('------\n')

        pairs = []
        for node in self.nodes:
            log.info('Cloudkick Node %s' % utils.node_to_str(node))
            msg, entity = self._get_or_create_entity_from_node(node)
            if msg:
                log.info('%s Rackspace Entity %s\n' % (msg, utils.entity_to_str(entity)))
                pairs.append((node, entity))
            else:
                log.info('Skipped')

        return pairs
