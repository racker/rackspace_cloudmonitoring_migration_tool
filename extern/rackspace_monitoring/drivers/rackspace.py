# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys

try:
    import simplejson as json
except:
    import json

from libcloud.utils.py3 import httplib, urlparse
from libcloud.common.types import MalformedResponseError, LibcloudError
from libcloud.common.types import LazyList
from libcloud.common.base import Response

from rackspace_monitoring.providers import Provider
from rackspace_monitoring.utils import to_underscore_separated
from rackspace_monitoring.utils import value_to_bool

from rackspace_monitoring.base import (MonitoringDriver, Entity,
                                      NotificationPlan, MonitoringZone,
                                      Notification, CheckType, Alarm, Check,
                                      NotificationType, AlarmChangelog,
                                      LatestAlarmState, Agent, AgentToken,
                                      AgentConnection)

from libcloud.common.rackspace import AUTH_URL_US
from libcloud.common.openstack import OpenStackBaseConnection

API_VERSION = 'v1.0'
API_URL = 'https://monitoring.api.rackspacecloud.com/%s' % (API_VERSION)


class RackspaceMonitoringValidationError(LibcloudError):

    def __init__(self, code, type, message, details, driver):
        self.code = code
        self.type = type
        self.message = message
        self.details = details
        super(RackspaceMonitoringValidationError, self).__init__(value=message,
                                                                 driver=driver)
    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        string = '<ValidationError type=%s, ' % (self.type)
        string += 'message="%s", details=%s>' % (self.message, self.details)
        return string.encode('utf-8')


class RackspaceMonitoringResponse(Response):

    valid_response_codes = [httplib.CONFLICT]

    def success(self):
        i = int(self.status)
        return i >= 200 and i <= 299 or i in self.valid_response_codes

    def parse_body(self):
        if not self.body:
            return None

        if 'content-type' in self.headers:
            key = 'content-type'
        elif 'Content-Type' in self.headers:
            key = 'Content-Type'
        else:
            raise LibcloudError('Missing content-type header')

        content_type = self.headers[key]
        if content_type.find(';') != -1:
            content_type = content_type.split(';')[0]

        if content_type == 'application/json':
            try:
                data = json.loads(self.body)
            except:
                raise MalformedResponseError('Failed to parse JSON',
                                             body=self.body,
                                             driver=RackspaceMonitoringDriver)
        elif content_type == 'text/plain':
            data = self.body
        else:
            data = self.body

        return data

    def parse_error(self):
        body = self.parse_body()
        if self.status == httplib.BAD_REQUEST:
            error = RackspaceMonitoringValidationError(message=body['message'],
                                               code=body['code'],
                                               type=body['type'],
                                               details=body['details'],
                                               driver=self.connection.driver)
            raise error

        return body


class RackspaceMonitoringConnection(OpenStackBaseConnection):
    """
    Base connection class for the Rackspace Monitoring driver.
    """

    type = Provider.RACKSPACE
    responseCls = RackspaceMonitoringResponse
    auth_url = AUTH_URL_US
    _url_key = "monitoring_url"

    def __init__(self, user_id, key, secure=False, ex_force_base_url=API_URL,
                 ex_force_auth_url=None, ex_force_auth_version='2.0'):
        self.api_version = API_VERSION
        self.monitoring_url = ex_force_base_url
        self.accept_format = 'application/json'
        super(RackspaceMonitoringConnection, self).__init__(user_id, key,
                                secure=secure,
                                ex_force_base_url=ex_force_base_url,
                                ex_force_auth_url=ex_force_auth_url,
                                ex_force_auth_version=ex_force_auth_version)

    def request(self, action, params=None, data='', headers=None, method='GET',
                raw=False):
        if not headers:
            headers = {}
        if not params:
            params = {}

        headers['Accept'] = 'application/json'

        if method in ['POST', 'PUT']:
            headers['Content-Type'] = 'application/json; charset=UTF-8'
            data = json.dumps(data)

        return super(RackspaceMonitoringConnection, self).request(
            action=action,
            params=params, data=data,
            method=method, headers=headers,
            raw=raw
        )


class RackspaceMonitoringDriver(MonitoringDriver):
    """
    Base Rackspace Monitoring driver.

    """
    name = 'Rackspace Monitoring'
    connectionCls = RackspaceMonitoringConnection

    def __init__(self, *args, **kwargs):
        self._ex_force_base_url = kwargs.pop('ex_force_base_url', None)
        self._ex_force_auth_url = kwargs.pop('ex_force_auth_url', None)
        self._ex_force_auth_version = kwargs.pop('ex_force_auth_version', None)
        super(RackspaceMonitoringDriver, self).__init__(*args, **kwargs)

        self.connection._populate_hosts_and_request_paths()
        ep = self.connection.service_catalog.get_endpoint(name='cloudServers',
                                               service_type='compute',
                                               region=None)

        tenant_id = ep['tenantId']
        self.connection._ex_force_base_url = '%s/%s' % (
                self.connection._ex_force_base_url, tenant_id)

    def _ex_connection_class_kwargs(self):
        rv = {}
        if self._ex_force_base_url:
            rv['ex_force_base_url'] = self._ex_force_base_url
        if self._ex_force_auth_url:
            rv['ex_force_auth_url'] = self._ex_force_auth_url
        if self._ex_force_auth_version:
            rv['ex_force_auth_version'] = self._ex_force_auth_version
        return rv

    def _get_more(self, last_key, value_dict):
        key = None

        params = value_dict.get('params', {})

        if not last_key:
            key = value_dict.get('start_marker')
        else:
            key = last_key

        if key:
            params['marker'] = key

        response = self.connection.request(value_dict['url'], params)

        # newdata, self._last_key, self._exhausted
        if response.status == httplib.NO_CONTENT:
            return [], None, False
        elif response.status == httplib.OK:
            resp = json.loads(response.body)
            l = None

            if 'list_item_mapper' in value_dict:
                func = value_dict['list_item_mapper']
                l = [func(x, value_dict) for x in resp['values']]
            else:
                l = value_dict['object_mapper'](resp, value_dict)
            m = resp['metadata'].get('next_marker')
            return l, m, m == None

        body = json.loads(response.body)

        details = body['details'] if 'details' in body else ''
        raise LibcloudError('Unexpected status code: %s (url=%s, details=%s)' %
                            (response.status, value_dict['url'], details))

    def _plural_to_singular(self, name):
        kv = {'entities': 'entity',
              'agent_tokens': 'agent_token',
              'agents': 'agent',
              'alarms': 'alarm',
              'checks': 'check',
              'notifications': 'notification',
              'notification_plans': 'notificationPlan',
              'tokens': 'token'}

        return kv[name]

    def _url_to_obj_ids(self, url):
        rv = {}
        path = urlparse.urlparse(url).path
        # removed duplicated slashes
        path = path.replace('//', '/')

        chunks = path.split('/')[1:]

        # We start from 2 because we want to ignore version and tenant id
        # which are firest and second part of the url component
        for i in range(2, len(chunks), 2):
            chunk = chunks[i]

            if not chunk:
                continue

            key = self._plural_to_singular(chunk) + '_id'
            key = to_underscore_separated(key)
            rv[key] = chunks[i + 1]

        return rv

    def _create(self, url, data, coerce):
        params = {}

        for k in data.keys():
            if data[k] is None:
                del data[k]

        if 'who' in data:
            if data['who'] is not None:
                params['_who'] = data['who']
            del data['who']

        if 'why' in data:
            if data['why'] is not None:
                params['_why'] = data['why']
            del data['why']

        resp = self.connection.request(url,
                                       method='POST',
                                       params=params,
                                       data=data)
        if resp.status == httplib.CREATED:
            location = resp.headers.get('location')
            if not location:
                raise LibcloudError('Missing location header')
            obj_ids = self._url_to_obj_ids(location)
            return coerce(**obj_ids)
        else:
            raise LibcloudError('Unexpected status code: %s' % (resp.status))

    def _update(self, url, data, kwargs, coerce):
        params = {}

        for k in data.keys():
            if data[k] is None:
                del data[k]

        if 'who' in kwargs and kwargs['who'] is not None:
            params['_who'] = kwargs['who']

        if 'why' in kwargs and kwargs['why'] is not None:
            params['_why'] = kwargs['why']

        resp = self.connection.request(url, method='PUT', params=params,
                                       data=data)

        if resp.status == httplib.NO_CONTENT:
            # location
            # /v1.0/{object_type}/{id}
            location = resp.headers.get('location')
            if not location:
                raise LibcloudError('Missing location header')

            obj_ids = self._url_to_obj_ids(location)
            return coerce(**obj_ids)
        else:
            raise LibcloudError('Unexpected status code: %s' % (resp.status))

    def _delete(self, url, kwargs=None):
        kwargs = kwargs or {}
        params = {}

        if 'who' in kwargs and kwargs['who'] is not None:
            params['_who'] = kwargs['who']

        if 'why' in kwargs and kwargs['why'] is not None:
            params['_why'] = kwargs['why']

        resp = self.connection.request(action=url, method='DELETE',
                                       params=params)
        return resp.status == httplib.NO_CONTENT

    def list_check_types(self):
        value_dict = {'url': '/check_types',
                       'list_item_mapper': self._to_check_type}

        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def _to_check_type(self, obj, value_dict):
        return CheckType(id=obj['id'],
                         fields=obj.get('fields', []),
                         is_remote=obj.get('type') == 'remote')

    def list_notification_types(self):
        value_dict = {'url': '/notification_types',
                       'list_item_mapper': self._to_notification_type}

        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def _to_notification_type(self, obj, value_dict):
        return NotificationType(id=obj['id'],
                         fields=obj.get('fields', []))

    def _to_monitoring_zone(self, obj, value_dict=None):
        return MonitoringZone(id=obj['id'], label=obj['label'],
                              country_code=obj['country_code'],
                              source_ips=obj['source_ips'],
                              driver=self)

    def list_monitoring_zones(self):
        value_dict = {'url': '/monitoring_zones',
                       'list_item_mapper': self._to_monitoring_zone}
        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def get_monitoring_zone(self, monitoring_zone_id):
        url = '/monitoring_zones/%s' % (monitoring_zone_id)
        resp = self.connection.request(url).object
        return self._to_monitoring_zone(obj=resp)

    ##########
    ## Alarms
    ##########

    def get_alarm(self, entity_id, alarm_id):
        url = "/entities/%s/alarms/%s" % (entity_id, alarm_id)
        resp = self.connection.request(url)
        return self._to_alarm(resp.object, {'entity_id': entity_id})

    def _to_alarm(self, alarm, value_dict):
        return Alarm(id=alarm['id'],
            check_type=alarm.get('check_type'),
            check_id=alarm.get('check_id'),
            criteria=alarm['criteria'],
            notification_plan_id=alarm['notification_plan_id'],
            extra=alarm['metadata'],
            driver=self, entity_id=value_dict['entity_id'])

    def list_alarms(self, entity, ex_next_marker=None):
        value_dict = {'url': '/entities/%s/alarms' % (entity.id),
                      'start_marker': ex_next_marker,
                      'list_item_mapper': self._to_alarm,
                      'entity_id': entity.id}

        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def list_alarm_changelog(self, ex_next_marker=None):
        value_dict = {'url': '/changelogs/alarms',
                      'start_marker': ex_next_marker,
                      'list_item_mapper': self._to_alarm_changelog}

        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def _to_alarm_changelog(self, values, value_dict):
        alarm_changelog = AlarmChangelog(id=values['id'],
                                       alarm_id=values['alarm_id'],
                                       entity_id=values['entity_id'],
                                       check_id=values['check_id'],
                                       previous_state=values['previous_state'],
                                       timestamp=values['timestamp'],
                                       state=values['state'])
        return alarm_changelog

    def delete_alarm(self, alarm, **kwargs):
        return self._delete(url="/entities/%s/alarms/%s" % (alarm.entity_id,
                                                            alarm.id),
                            kwargs=kwargs)

    def update_alarm(self, alarm, data, **kwargs):
        return self._update("/entities/%s/alarms/%s" % (alarm.entity_id,
                                                        alarm.id),
            data=data, kwargs=kwargs, coerce=self.get_alarm)

    def create_alarm(self, entity, **kwargs):
        data = {'who': kwargs.get('who'),
                'why': kwargs.get('why'),
                'check_type': kwargs.get('check_type'),
                'check_id': kwargs.get('check_id'),
                'criteria': kwargs.get('criteria'),
                'metadata': kwargs.get('metadata'),
                'notification_plan_id': kwargs.get('notification_plan_id')}

        return self._create("/entities/%s/alarms" % (entity.id),
            data=data, coerce=self.get_alarm)

    def test_alarm(self, entity, **kwargs):
        data = {'criteria': kwargs.get('criteria'),
                'check_data': kwargs.get('check_data')}
        resp = self.connection.request("/entities/%s/test-alarm" % (entity.id),
                                       method='POST',
                                       data=data)
        return resp.object

    ####################
    ## Notifications
    ####################

    def list_notifications(self, ex_next_marker=None):
        value_dict = {'url': '/notifications',
                      'start_marker': ex_next_marker,
                      'list_item_mapper': self._to_notification}

        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def _to_notification(self, notification, value_dict):
        return Notification(id=notification['id'], label=notification['label'],
                            type=notification['type'],
                            details=notification['details'], driver=self)

    def get_notification(self, notification_id):
        resp = self.connection.request("/notifications/%s" % (notification_id))

        return self._to_notification(resp.object, {})

    def delete_notification(self, notification, **kwargs):
        return self._delete(url="/notifications/%s" % (notification.id),
                            kwargs=kwargs)

    def update_notification(self, notification, data, **kwargs):
        return self._update('/notifications/%s' % (notification.id),
            data=data, kwargs=kwargs, coerce=self.get_notification)

    def create_notification(self, **kwargs):
        data = {'who': kwargs.get('who'),
                'why': kwargs.get('why'),
                'label': kwargs.get('label'),
                'type': kwargs.get('type'),
                'details': kwargs.get('details')}

        return self._create("/notifications", data=data,
                            coerce=self.get_notification)

    def test_existing_notification(self, notification):
        resp = self.connection.request('/notifications/%s/test' % (notification.id),
                                       method='POST')
        return resp.object

    def test_notification(self, **kwargs):
        data = {'who': kwargs.get('who'),
                'why': kwargs.get('why'),
                'type': kwargs.get('type'),
                'details': kwargs.get('details')}
        resp = self.connection.request('/test-notification', method='POST', data=data)
        return resp.object


    ####################
    ## Notification Plan
    ####################

    def _to_notification_plan(self, notification_plan, value_dict):
        critical_state = notification_plan.get('critical_state', [])
        warning_state = notification_plan.get('warning_state', [])
        ok_state = notification_plan.get('ok_state', [])
        return NotificationPlan(id=notification_plan['id'],
            label=notification_plan['label'],
            critical_state=critical_state, warning_state=warning_state,
            ok_state=ok_state, driver=self)

    def get_notification_plan(self, notification_plan_id):
        resp = self.connection.request("/notification_plans/%s" % (
            notification_plan_id))
        return self._to_notification_plan(resp.object, {})

    def delete_notification_plan(self, notification_plan, **kwargs):
        return self._delete(url="/notification_plans/%s" %
                            (notification_plan.id),
                            kwargs=kwargs)

    def list_notification_plans(self, ex_next_marker=None):
        value_dict = {'url': "/notification_plans",
                      'start_marker': ex_next_marker,
                      'list_item_mapper': self._to_notification_plan}
        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def update_notification_plan(self, notification_plan, data, **kwargs):
        return self._update("/notification_plans/%s" % (notification_plan.id),
            data=data, kwargs=kwargs,
            coerce=self.get_notification_plan)

    def create_notification_plan(self, **kwargs):
        data = {'who': kwargs.get('who'),
                'why': kwargs.get('why'),
                'label': kwargs.get('label'),
                'critical_state': kwargs.get('critical_state', []),
                'warning_state': kwargs.get('warning_state', []),
                'ok_state': kwargs.get('ok_state', []),
                }
        return self._create("/notification_plans", data=data,
                            coerce=self.get_notification_plan)

    ###########
    ## Checks
    ###########

    def get_check(self, entity_id, check_id):
        resp = self.connection.request('/entities/%s/checks/%s' % (entity_id,
                                                                   check_id))
        return self._to_check(resp.object, {'entity_id': entity_id})

    def _to_check(self, obj, value_dict):
        return Check(**{
            'id': obj['id'],
            'label': obj.get('label'),
            'timeout': obj['timeout'],
            'period': obj['period'],
            'monitoring_zones': obj['monitoring_zones_poll'],
            'target_alias': obj.get('target_alias', None),
            'target_hostname': obj.get('target_hostname', None),
            'target_resolver': obj.get('target_resolver', None),
            'type': obj['type'],
            'details': obj.get('details', {}),
            'disabled': value_to_bool(obj.get('disabled', '0')),
            'driver': self,
            'entity_id': value_dict['entity_id'],
            'extra': obj['metadata']})

    def list_checks(self, entity, ex_next_marker=None):
        value_dict = {'url': "/entities/%s/checks" % (entity.id),
                      'start_marker': ex_next_marker,
                      'list_item_mapper': self._to_check,
                      'entity_id': entity.id}
        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def _check_kwarg_to_data(self, kwargs):
        filtered = {}
        data = {'who': kwargs.get('who'),
                'why': kwargs.get('why'),
                'label': kwargs.get('label'),
                'monitoring_zones_poll': kwargs.get('monitoring_zones', None),
                'target_alias': kwargs.get('target_alias'),
                'target_resolver': kwargs.get('target_resolver'),
                'target_hostname': kwargs.get('target_hostname'),
                'type': kwargs.get('type'),
                'disabled': kwargs.get('disabled', None),
                'details': kwargs.get('details'),
                'metadata': kwargs.get('metadata', {})
                }

        if 'period' in kwargs:
            data['period'] = kwargs['period']

        if 'timeout' in kwargs:
            data['timeout'] = kwargs['timeout']

        for k in data.keys():
            if data[k] is not None:
                filtered[k] = data[k]

        return filtered

    def test_check(self, entity, **kwargs):
        data = self._check_kwarg_to_data(kwargs)
        resp = self.connection.request('/entities/%s/test-check' % (entity.id),
                                       method='POST',
                                       data=data)
        return resp.object

    def test_existing_check(self, check, **kwargs):
        resp = self.connection.request('/entities/%s/checks/%s/test' %
                                       (check.entity_id, check.id),
                                       method='POST')
        return resp.object

    def create_check(self, entity, **kwargs):
        data = self._check_kwarg_to_data(kwargs)
        return self._create("/entities/%s/checks" % (entity.id),
            data=data, coerce=self.get_check)

    def update_check(self, check, data, **kwargs):
        data = self._check_kwarg_to_data(kwargs=data)
        return self._update("/entities/%s/checks/%s" % (check.entity_id,
                                                        check.id),
            data=data, kwargs=kwargs, coerce=self.get_check)

    def delete_check(self, check, **kwargs):
        return self._delete(url="/entities/%s/checks/%s" %
                            (check.entity_id, check.id),
                            kwargs=kwargs)

    ###########
    ## Entity
    ###########

    def get_entity(self, entity_id):
        resp = self.connection.request("/entities/%s" % (entity_id))
        return self._to_entity(resp.object, {})

    def _to_entity(self, entity, value_dict):
        ips = []
        ipaddrs = entity.get('ip_addresses', {})
        if ipaddrs is not None:
            for key in ipaddrs.keys():
                ips.append((key, ipaddrs[key]))
        return Entity(id=entity['id'], label=entity['label'],
                      extra=entity['metadata'], driver=self,
                      agent_id=entity.get('agent_id'), ip_addresses=ips)

    def delete_entity(self, entity, **kwargs):
        return self._delete(url="/entities/%s" % (entity.id),
                            kwargs=kwargs)

    def list_entities(self, ex_next_marker=None):
        value_dict = {'url': '/entities',
                      'start_marker': ex_next_marker,
                      'list_item_mapper': self._to_entity}

        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def create_entity(self, **kwargs):
        data = {'who': kwargs.get('who'),
                'why': kwargs.get('why'),
                'ip_addresses': kwargs.get('ip_addresses', {}),
                'label': kwargs.get('label'),
                'metadata': kwargs.get('extra', {}),
                'agent_id': kwargs.get('agent_id')}

        return self._create("/entities", data=data, coerce=self.get_entity)

    def update_entity(self, entity, data, **kwargs):
        return self._update("/entities/%s" % (entity.id),
            data=data, kwargs=kwargs, coerce=self.get_entity)

    def usage(self):
        resp = self.connection.request("/usage")
        return resp.object

    def _to_audit(self, audit, value_dict):
        return audit

    def list_audits(self, start_from=None, to=None):
        # TODO: add start/end date support
        value_dict = {'url': '/audits',
                      'params': {'limit': 200},
                      'list_item_mapper': self._to_audit}

        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def get_entity_host_info(self, entity_id, info_type):
        url = "/entities/%s/agent/host_info/%s" % (entity_id, info_type)
        resp = self.connection.request(url)
        return resp.object

    # Agent tokens

    def list_agent_tokens(self):
        value_dict = {'url': '/agent_tokens',
                      'list_item_mapper': self._to_agent_token}

        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def get_agent_token(self, agent_token_id):
        url = "/agent_tokens/%s" % (agent_token_id)
        resp = self.connection.request(url)
        return self._to_agent_token(resp.object, {})

    def create_agent_token(self, label=None, **kwargs):
        data = {'label': label,
                'who': kwargs.get('who'),
                'why': kwargs.get('why')}

        return self._create('/agent_tokens', data=data,
                            coerce=self.get_agent_token)

    def delete_agent_token(self, agent_token, **kwargs):
        return self._delete(url="/agent_tokens/%s" % (agent_token.id),
                            kwargs=kwargs)

    def _to_agent_token(self, agent_token, value_dict):
        return AgentToken(id=agent_token['id'], label=agent_token['label'],
                          token=agent_token['token'])

    # Agent

    def _to_agents(self, agent, value_dict):
        return Agent(id=agent['id'], last_connected=agent['last_connected'])

    def _to_agent_connection(self, conn, value_dict):
        return AgentConnection(id=conn['id'], endpoint=conn['endpoint'],
            agent_id=conn['agent_id'], bundle_version=conn['bundle_version'],
            process_version=conn['process_version'], agent_ip=conn['agent_ip'])

    def list_agents(self):
        value_dict = {'url': '/agents',
                      'list_item_mapper': self._to_agents}

        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def list_agent_connections(self, agent_id):
        value_dict = {'url': "/agents/%s/connections" % (agent_id),
                      'list_item_mapper': self._to_agent_connection}

        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def get_agent_host_info(self, agent_id, info_type):
        url = "/agents/%s/host_info/%s" % (agent_id, info_type)
        resp = self.connection.request(url)
        return resp.object

    #########
    ## Other
    #########

    def test_check_and_alarm(self, entity, criteria, **kwargs):
        check_data = self.test_check(entity=entity, **kwargs)
        data = {'criteria': criteria, 'check_data': check_data}
        result = self.test_alarm(entity=entity, **data)
        return result

    ####################
    # Extension methods
    ####################

    def ex_list_alarm_notification_history_checks(self, entity, alarm):
        resp = self.connection.request(
                '/entities/%s/alarms/%s/notification_history' %
                                       (entity.id, alarm.id)).object
        return resp

    def ex_list_alarm_notification_history(self, entity, alarm, check,
                                           ex_next_marker=None):
        value_dict = {'url': '/entities/%s/alarms/%s/notification_history/%s' %
                              (entity.id, alarm.id, check.id),
               'list_item_mapper': self._to_alarm_notification_history_obj}
        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def _to_alarm_notification_history_obj(self, values, value_dict):
        return values

    def ex_delete_checks(self, entity):
        # Delete all Checks for an entity
        checks = self.list_checks(entity=entity)
        for check in checks:
            self.delete_check(check=check)

    def ex_delete_alarms(self, entity):
        # Delete all Alarms for an entity
        alarms = self.list_alarms(entity=entity)
        for alarm in alarms:
            self.delete_alarm(alarm=alarm)

    def ex_limits(self):
        resp = self.connection.request('/limits',
                                       method='GET')
        return resp.object

    def ex_views_overview(self, ex_next_marker=None):
        value_dict = {'url': '/views/overview',
                      'start_marker': ex_next_marker,
                      'list_item_mapper': self._to_overview_obj}

        return LazyList(get_more=self._get_more, value_dict=value_dict)

    def ex_traceroute(self, monitoring_zone, target, target_resolver='IPv4'):
        data = {'target': target, 'target_resolver': target_resolver}
        path = '/monitoring_zones/%s/traceroute' % (monitoring_zone.id)
        resp = self.connection.request(path, data=data, method='POST').object
        return resp['result']

    def _to_latest_alarm_state(self, obj, value_dict):
        return LatestAlarmState(entity_id=obj['entity_id'],
                check_id=obj['check_id'], alarm_id=obj['alarm_id'],
                timestamp=obj['timestamp'], state=obj['state'])

    def _to_overview_obj(self, data, value_dict):
        entity = self._to_entity(data['entity'], {})

        child_value_dict = {'entity_id': entity.id}
        checks = [self._to_check(check, child_value_dict) for check
                  in data['checks']]
        alarms = [self._to_alarm(alarm, child_value_dict) for alarm
                  in data['alarms']]
        latest_alarm_states = [self._to_latest_alarm_state(item, {}) for item
                               in data['latest_alarm_states']]

        obj = {'entity': entity, 'checks': checks, 'alarms': alarms,
               'latest_alarm_states': latest_alarm_states}
        return obj
