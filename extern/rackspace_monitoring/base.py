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

# Backward compatibility for Python 2.5
from __future__ import with_statement

from libcloud.common.base import ConnectionUserAndKey


class MonitoringZone(object):
    """
    Represents a location from where the entities are monitored.
    """

    def __init__(self, id, label, country_code, source_ips, driver,
                 extra=None):
        self.id = id
        self.label = label
        self.country_code = country_code
        self.source_ips = source_ips
        self.driver = driver
        self.extra = extra or {}

    def __repr__(self):
        return ('<MonitoringZone: id=%s label=%s provider=%s ...>' %
                (self.id, self.label, self.driver.name)).encode('utf-8')


class Entity(object):
    """
    Represents an entity to be monitored.
    """

    def __init__(self, id, label, ip_addresses, agent_id, driver, extra=None):
        """
        @type label: C{str}
        @param label: Object label (must be unique per container).

        @type extra: C{dict}
        @param extra: Extra attributes.

        @type ip_addresses: C{list}
        @param ip_addresses: List of String aliases to IP Addresses tuples.

        @type driver: C{StorageDriver}
        @param driver: StorageDriver instance.
        """
        self.id = id
        self.label = label
        self.extra = extra or {}
        self.ip_addresses = ip_addresses or []
        self.agent_id = agent_id
        self.driver = driver

    def update(self, data):
        self.driver.update_entity(entity=self, data=data)

    def delete(self):
        return self.driver.delete_entity(self)

    def __repr__(self):
        return ('<Entity: id=%s label=%s provider=%s ...>' %
                (self.id, self.label, self.driver.name)).encode('utf-8')


class Notification(object):
    def __init__(self, id, label, type, details, driver=None):
        self.id = id
        self.label = label
        self.type = type
        self.details = details
        self.driver = driver

    def update(self, data):
        self.driver.update_notification(notification=self, data=data)

    def delete(self):
        return self.driver.delete_notification(self)

    def __repr__(self):
        return ('<Notification: id=%s, label=%s, type=%s ...>' % (self.id,
                 self.label, self.type)).encode('utf-8')


class NotificationPlan(object):
    """
    Represents a notification plan.
    """
    def __init__(self, id, label, driver, critical_state=None,
                 warning_state=None, ok_state=None):
        self.id = id
        self.label = label
        self.critical_state = critical_state
        self.warning_state = warning_state
        self.ok_state = ok_state
        self.driver = driver

    def update(self, data):
        self.driver.update_notification_plan(notification_plan=self, data=data)

    def delete(self):
        return self.driver.delete_notification_plan(self)

    def __repr__(self):
        return ('<NotificationPlan: id=%s...>' % (self.id)).encode('utf-8')


class CheckType(object):
    def __init__(self, id, fields, is_remote):
        self.id = id
        self.is_remote = is_remote
        self.fields = fields

    def __repr__(self):
        return ('<CheckType: id=%s ...>' % (self.id)).encode('utf-8')


class NotificationType(object):
    def __init__(self, id, fields):
        self.id = id
        self.fields = fields

    def __repr__(self):
        return ('<NotificationType: id=%s ...>' % (self.id)).encode('utf-8')


class Alarm(object):
    def __init__(self, id, criteria, driver, entity_id, extra,
                 check_type=None, check_id=None, notification_plan_id=None):
        #import ipdb; ipdb.set_trace()
        self.id = id
        self.check_type = check_type
        self.check_id = check_id
        self.criteria = criteria
        self.driver = driver
        self.notification_plan_id = notification_plan_id
        self.entity_id = entity_id
        self.extra = extra or {}

    def update(self, data):
        self.driver.update_alarm(alarm=self, data=data)

    def delete(self):
        return self.driver.delete_alarm(self)

    def __repr__(self):
        return ('<Alarm: id=%s ...>' % (self.id)).encode('utf-8')


class Check(object):
    def __init__(self, id, label, timeout, period, monitoring_zones,
                 target_alias, target_hostname, target_resolver, type, details,
                 entity_id, disabled, extra, driver):
        self.id = id
        self.label = label
        self.timeout = timeout
        self.period = period
        self.monitoring_zones = monitoring_zones
        self.target_alias = target_alias
        self.target_hostname = target_hostname
        self.target_resolver = target_resolver
        self.type = type
        self.details = details
        self.entity_id = entity_id
        self.disabled = disabled
        self.driver = driver
        self.extra = extra or {}

    def update(self, data):
        self.driver.update_check(check=self, data=data)

    def delete(self):
        return self.driver.delete_check(self)

    def __repr__(self):
        return ('<Check: id=%s label=%s...>' % (self.id, self.label)).encode('utf-8')


class AlarmChangelog(object):

    def __init__(self, id, alarm_id, entity_id, check_id, previous_state,
                 state, timestamp):
        self.id = id
        self.alarm_id = alarm_id
        self.entity_id = entity_id
        self.check_id = check_id
        self.previous_state = previous_state
        self.state = state
        self.timestamp = timestamp

    def __repr__(self):
        return ('<AlarmChangelog: id=%s alarm_id=%s, state=%s...>' % (
          self.id, self.alarm_id, self.state)).encode('utf-8')


class LatestAlarmState(object):
    def __init__(self, entity_id, check_id, alarm_id, timestamp, state):
        self.entity_id = entity_id
        self.check_id = check_id
        self.alarm_id = alarm_id
        self.timestamp = timestamp
        self.state = state

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return ('<LatestAlarmState: entity_id=%s, check_id=%s, alarm_id=%s, '
                'state=%s ...>' %
                (self.entity_id, self.check_id, self.alarm_id, self.state)) \
                .encode('utf-8')


class AgentToken(object):
    def __init__(self, id, label, token):
        self.id = id
        self.label = label
        self.token = token

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return ('<AgentToken: id=%s, label=%s, token=%s>' %
                (self.id, self.label, self.token)).encode('utf-8')

class Agent(object):
    def __init__(self, id, last_connected):
        self.id = id
        self.last_connected = last_connected

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return ('<Agent: id=%s, last_connected=%s>' %
            (self.id, self.last_connected)).encode('utf-8')

class AgentConnection(object):
    def __init__(self, id, endpoint, agent_id, bundle_version, process_version, agent_ip):
        self.id = id
        self.endpoint = endpoint
        self.agent_id = agent_id
        self.bundle_version = bundle_version
        self.process_version = process_version
        self.agent_ip = agent_ip

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return ('<AgentConnection: id=%s, agent_id=%s>' %
            (self.id, self.agent_id)).encode('utf-8')

class MonitoringDriver(object):
    """
    A base MonitoringDriver to derive from.
    """

    connectionCls = ConnectionUserAndKey
    name = None

    def __init__(self, key, secret=None, secure=True, host=None, port=None):
        self.key = key
        self.secret = secret
        self.secure = secure
        args = [self.key]

        if self.secret != None:
            args.append(self.secret)

        args.append(secure)

        if host != None:
            args.append(host)

        if port != None:
            args.append(port)

        self.connection = self.connectionCls(*args,
                                         **self._ex_connection_class_kwargs())

        self.connection.driver = self
        self.connection.connect()

    def _ex_connection_class_kwargs(self):
        return {}

    def list_entities(self):
        raise NotImplementedError(
            'list_entities not implemented for this driver')

    def list_checks(self):
        raise NotImplementedError(
            'list_checks not implemented for this driver')

    def list_check_types(self):
        raise NotImplementedError(
            'list_check_types not implemented for this driver')

    def list_monitoring_zones(self):
        raise NotImplementedError(
            'list_monitoring_zones not implemented for this driver')

    def list_notifications(self):
        raise NotImplementedError(
            'list_notifications not implemented for this driver')

    def list_notification_plans(self):
        raise NotImplementedError(
            'list_notification_plans not implemented for this driver')

    def delete_entity(self, entity):
        raise NotImplementedError(
            'delete_entity not implemented for this driver')

    def delete_check(self, check):
        raise NotImplementedError(
            'delete_check not implemented for this driver')

    def delete_alarm(self, check):
        raise NotImplementedError(
            'delete_alarm not implemented for this driver')

    def delete_notification(self, notification):
        raise NotImplementedError(
            'delete_notification not implemented for this driver')

    def delete_notification_plan(self, notification_plan):
        raise NotImplementedError(
            'delete_notification_plan not implemented for this driver')

    def create_check(self, **kwargs):
        raise NotImplementedError(
            'create_check not implemented for this driver')

    def create_alarm(self, **kwargs):
        raise NotImplementedError(
            'create_alarm not implemented for this driver')

    def create_entity(self, **kwargs):
        raise NotImplementedError(
            'create_entity not implemented for this driver')

    def create_notification(self, **kwargs):
        raise NotImplementedError(
            'create_notification not implemented for this driver')

    def create_notification_plan(self, **kwargs):
        raise NotImplementedError(
            'create_notification_plan not implemented for this driver')

    def update_entity(self, entity, data):
        raise NotImplementedError(
            'update_entity not implemented for this driver')

    def update_check(self, check, data):
        raise NotImplementedError(
            'update_check not implemented for this driver')

    def update_alarm(self, alarm, data):
        raise NotImplementedError(
            'update_alarm not implemented for this driver')

    def update_notification(self, notification, data):
        raise NotImplementedError(
            'update_notification not implemented for this driver')

    def update_notification_plan(self, notification_plan, data):
        raise NotImplementedError(
            'update_notification_plan not implemented for this driver')
