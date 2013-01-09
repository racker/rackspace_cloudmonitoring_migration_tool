import pprint

from copy import copy

import utils
import logging


class MigratedEntity(object):
    """
    CK Node --> RS Entity
    """
    ck_api = None
    rs_api = None

    ck_node = None  # extern/cloudkick_api/wrapper.py:Node instance
    rs_entity = None  # extern/libcloud/rackspace_monitoring/base.py:Entity instance

    migrated_checks = None

    _entity_cache = None  # dict - JSON serializable and suitable for using with the RSC entity API
    _rs_entities_cache = None  # list - a rs_api.list_entities() call, you can pass in the results as a cache

    def __init__(self, migrator, ck_node):
        self.migrator = migrator

        self.ck_api = migrator.ck_api
        self.rs_api = migrator.rs_api

        self.ck_node = ck_node

        # API call caches
        self._rs_alarms_cache = None
        self._rs_checks_cache = None

        # find suitable existing entity
        self.rs_entity = self._find_entity()

        # JSON-serializable dict suitable for using with rs_api
        self._entity_cache = {}
        self._populate_entity()

        # list of checks applied to this entity
        self.migrated_checks = []

    def __str__(self):
        return pprint.pformat(self._cache)

    def get_rs_alarms(self):
        if not self._rs_alarms_cache:
            self._rs_alarms_cache = self.rs_api.list_alarms(self.rs_entity)
        return self._rs_alarms_cache

    def get_rs_checks(self):
        if not self._rs_checks_cache:
            self._rs_checks_cache = self.rs_api.list_checks(self.rs_entity)
        return self._rs_checks_cache

    def _populate_entity(self):
        """
        returns base entity dict
        """
        self._entity_cache['label'] = self.ck_node.label
        self._entity_cache['ip_addresses'] = self.ck_node.ip_addresses
        self._entity_cache['agent_id'] = self.ck_node.label
        self._entity_cache['metadata'] = {'ck_node_id': self.ck_node.id}

    def _find_entity(self):
        """
        finds a matching rs node for this entity (if one exists)
        """
        for e in self.migrator.get_rs_entities():
            # check in the entity metadata for ck_node_id
            if self.ck_node.id == e.extra.get('ck_node_id'):
                return e

            # find any matching *public* ips
            public_entity_ips = [ip for label, ip in e.ip_addresses if 'public' in label]
            public_node_ips = [ip for label, ip in self.ck_node.ip_addresses.items() if 'public' in label]
            for ip in public_node_ips:
                if ip in public_entity_ips:
                    return e
        return None

    def save(self, commit=True):
        """
        Calculate the difference between reality and the entity upstream. Create/Update
        entities as needed.

        @param rs_api obj - instance of the monitoring libcloud driver, if it's not given
                            the diff is still calculaed and returned but no changes are saved
        """
        # if we never found a matching entity, we can just create it
        if not self.rs_entity:
            if commit:
                e = copy(self._entity_cache)
                e['extra'] = e.pop('metadata')
                self.rs_entity = self.rs_api.create_entity(**e)
            return 'Created', self._entity_cache

        # check for different fields on the upstream object
        e = copy(self._entity_cache)

        e.pop('label')  # don't actually update label

        entity_ips = dict(self.rs_entity.ip_addresses)
        for k, v in entity_ips.items():
            if v == e['ip_addresses'].get(k):
                e['ip_addresses'].pop(k)

        if not e['ip_addresses']:
            e.pop('ip_addresses')

        # leave the rest of the metadata alone
        if e['metadata'].get('ck_node_id') == self.rs_entity.extra.get('ck_node_id'):
            e.pop('metadata')

        if e.get('agent_id') == self.rs_entity.agent_id:
            e.pop('agent_id')

        if e:
            if commit:
                self.rs_entity = self.rs_api.update_entity(self.rs_entity, e)
            return 'Updated', e

        return 'Unchanged', None


class EntityMigrator(object):

    def __init__(self, migrator, logger=None):
        self.logger = logger
        if not self.logger:
            self.logger = logging.getLogger('maas_migration')

        self.migrator = migrator

        self.ck_api = self.migrator.ck_api
        self.rs_api = self.migrator.rs_api

        self.dry_run = self.migrator.options.dry_run
        self.auto = self.migrator.options.auto

    def migrate(self):
        """
        adds or updates entities in rs from nodes in ck
        """
        self.logger.info('\nEntities')
        self.logger.info('------\n')

        for ck_node in self.ck_api.list_nodes():
            self.logger.info('Migrating Cloudkick Node - %s' % ck_node)

            # set up obj and see if there are any changes necessary
            entity = MigratedEntity(self.migrator, ck_node)
            action, result = entity.save(commit=False)

            # print action and prompt for commit
            if action == 'Created':
                self.logger.info('Creating new entity:\n%s' % (pprint.pformat(result)))
                if self.auto or utils.get_input('Create this entity?', options=['y', 'n'], default='y') == 'y':
                    try:
                        entity.save()
                    except Exception as e:
                        self.logger.error('Exception creating entity:\n%s' % e)
                    else:
                        self.migrator.migrated_entities.append(entity)
            elif action == 'Updated':
                self.logger.info('Updating entity %s - changes:\n%s' % (entity.rs_entity.id, pprint.pformat(result)))
                if self.auto or utils.get_input('Update this entity?', options=['y', 'n'], default='y') == 'y':
                    try:
                        entity.save()
                    except Exception as e:
                        self.logger.error('Exception updating entity:\n%s' % e)
                    else:
                        self.migrator.migrated_entities.append(entity)
            else:
                self.logger.info('No changes needed for entity %s' % (entity.rs_entity.id))
                self.migrator.migrated_entities.append(entity)

            self.logger.info('')
