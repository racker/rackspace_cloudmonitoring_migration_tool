import mock

# API types
from cloudkick_api.wrapper import Node
from rackspace_monitoring.base import Entity


class MockData(object):

    @classmethod
    def get_fake_api_node(cls, set_id='nFAKEID'):
        """
        Mock Cloudkick API node
        """
        return {'agent_name': None,
                'agent_status': u'connected',
                'color': None,
                'details': {'flavorId': ['4'],
                             'hostId': ['u23yhtui32hotuighlkd'],
                             'imageId': ['119'],
                             'lcid': ['3453232'],
                             'ssh_port': ['22'],
                             'ssh_user': ['blahbalh'],
                             'uri': ['https://servers.api.rackspacecloud.com/v1.0/f4314321servers/2314']},
                'id': set_id,
                'ipaddress': '50.50.50.50',
                'is_active': True,
                'name': 'FAKE_NAME',
                'private_ips': ['1.2.3.4', '5.6.7.8'],
                'provider': {'api_key': 'afdsa',
                              'id': 'peqr32134',
                              'is_active': 1,
                              'name': 'Rackspace',
                              'type': {'code': 5, 'description': 'RACKSPACE'}},
                'public_ips': ['50.50.50.50', '60.60.60.60'],
                'status': {'code': 2, 'description': 'running'},
                'tags': [{'created_at': 1310076269,
                           'id': 't7813ee071',
                           'name': 'agent'},
                          {'created_at': 1313084592,
                           'id': 'tdf14fdab3',
                           'name': 'apache'},
                          {'created_at': 1308184031,
                           'id': 't5eeb6d138',
                           'name': 'linux'}]}

    @classmethod
    def get_fake_node(cls, set_id='nFAKEID'):
        """
        Mock wrapped Cloudkick Node
        """
        return Node(cls.get_fake_api_node(set_id))

    @classmethod
    def get_fake_entity(cls):
        kwargs = {
            'id': 'nFAKEID',
            'label': 'FAKE_LABEL',
            'ip_addresses': [('public0_v4', '50.50.50.50'),
                             ('public1_v4', '60.60.60.60'),
                             ('private0_v4', '1.2.3.4'),
                             ('private1_v4', '5.6.7.8')],
            'agent_id': 'nFAKEID',
            'extra': {'ck_node_id': 'nFAKEID'},
            'driver': mock.Mock()
        }
        return Entity(**kwargs)
