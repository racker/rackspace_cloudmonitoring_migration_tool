import unittest
import mock

from tests.utils import MockData

from cloudkick_api.wrapper import Node
from entities import MigratedEntity
from entities import EntityMigrator


class CloudkickNodeTests(unittest.TestCase):
    """
    Test the small API wrapper around the Cloudkick API library
    """
    def test_wrapper(self):
        # init wrapper with fake API data
        fake_api_node = MockData.get_fake_api_node()
        node = Node(fake_api_node)

        # assert everything is okay
        self.assertEquals(node.id, fake_api_node.get('id'))
        self.assertEquals(node.label, fake_api_node.get('name'))
        self.assertEquals(node.agent_id, fake_api_node.get('id'))
        self.assertEquals(node.extra, {})
        self.assertEquals(node.ip_addresses, {'public0_v4': '50.50.50.50',
                                              'private1_v4': '5.6.7.8',
                                              'private0_v4': '1.2.3.4',
                                              'public1_v4': '60.60.60.60'})

        fake_api_node['name'] = 'NEWNAME'
        node = Node(fake_api_node)

        # assert everything is okay
        self.assertEquals(node.id, fake_api_node.get('id'))
        self.assertEquals(node.label, fake_api_node.get('name'))
        self.assertEquals(node.agent_id, fake_api_node.get('id'))
        self.assertEquals(node.extra, {})
        self.assertEquals(node.ip_addresses, {'public0_v4': '50.50.50.50',
                                              'private1_v4': '5.6.7.8',
                                              'private0_v4': '1.2.3.4',
                                              'public1_v4': '60.60.60.60'})


class MigratedEntityTests(unittest.TestCase):

    def test_migrated_entity_new(self):
        e = MigratedEntity(mock.Mock(), mock.Mock(), MockData.get_fake_node())

        action, result = e.save()

        self.assertEquals(action, 'Created')
        self.assertEquals(result, {'agent_id': 'nFAKEID',
                                   'ip_addresses': {'private0_v4': '1.2.3.4',
                                                    'private1_v4': '5.6.7.8',
                                                    'public0_v4': '50.50.50.50',
                                                    'public1_v4': '60.60.60.60'},
                                    'label': 'FAKE_NAME',
                                    'metadata': {'ck_node_id': 'nFAKEID'}})

    def test_migrated_entity_update(self):
        fake_node = MockData.get_fake_node('nNEWID')
        e = MigratedEntity(mock.Mock(), mock.Mock(), fake_node, MockData.get_fake_entity())

        action, result = e.save()

        self.assertEquals(action, 'Updated')
        self.assertEquals(result, {'agent_id': 'nNEWID', 'metadata': {'ck_node_id': 'nNEWID'}})

    def test_migrated_entity_unchanged(self):
        e = MigratedEntity(mock.Mock(), mock.Mock(), MockData.get_fake_node(), MockData.get_fake_entity())

        action, result = e.save()

        self.assertEquals(action, 'Unchanged')
        self.assertEquals(result, None)


class EntityMigratorTests(unittest.TestCase):

    def setUp(self):
        self.rs_api = mock.Mock()
        self.ck_api = mock.Mock()

        self.rs_api.list_entities.return_value = []
        self.ck_api.list_nodes.return_value = []

    def test_no_nodes(self):
        migrator = EntityMigrator(self.ck_api, self.rs_api, auto=True, logger=mock.Mock())

        entities = migrator.migrate()
        self.assertEquals(entities, [])
        self.assertEquals(self.rs_api.update_entity.call_count, 0)
        self.assertEquals(self.rs_api.create_entity.call_count, 0)

    def test_new(self):
        self.ck_api.list_nodes.return_value = [MockData.get_fake_node()]

        migrator = EntityMigrator(self.ck_api, self.rs_api, auto=True, logger=mock.Mock())
        entities = migrator.migrate()
        self.assertEquals(len(entities), 1)
        self.assertEquals(self.rs_api.update_entity.call_count, 0)
        self.assertEquals(self.rs_api.create_entity.call_count, 1)

    def test_updates(self):
        fake_node = MockData.get_fake_node()
        fake_node.id = 'NEWID'
        self.ck_api.list_nodes.return_value = [fake_node]
        self.rs_api.list_entities.return_value = [MockData.get_fake_entity()]

        migrator = EntityMigrator(self.ck_api, self.rs_api, auto=True, logger=mock.Mock())
        entities = migrator.migrate()
        self.assertEquals(len(entities), 1)
        self.assertEquals(self.rs_api.update_entity.call_count, 1)
        self.assertEquals(self.rs_api.create_entity.call_count, 0)

    def test_mixed(self):
        # Should be unchanged
        unchanged_node = MockData.get_fake_node()
        unchanged_entity = MockData.get_fake_entity()

        # should get created
        new_node = MockData.get_fake_node('NEWID')
        new_node.ip_addresses = {"public0_v4": "totally_different_ip"}

        # should get updated
        updated_node = MockData.get_fake_node('NEWID2')
        updated_node.ip_addresses = {"public0_v4": "updated"}
        updated_entity = MockData.get_fake_entity()
        updated_entity.ip_addresses = [("public0_v4", "updated")]

        self.ck_api.list_nodes.return_value = [unchanged_node, updated_node, new_node]
        self.rs_api.list_entities.return_value = [unchanged_entity, updated_entity]

        migrator = EntityMigrator(self.ck_api, self.rs_api, auto=True, logger=mock.Mock())
        entities = migrator.migrate()

        self.assertEquals(len(entities), 3)
        self.assertEquals(self.rs_api.update_entity.call_count, 1)
        self.assertEquals(self.rs_api.create_entity.call_count, 1)
