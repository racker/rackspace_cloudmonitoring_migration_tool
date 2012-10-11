import pprint

from translator import translate

import utils
import logging

from copy import copy

_consistency_levels = ['ALL', 'ONE', 'QUORUM']


class MigratedAlarm(object):

    ck_api = None
    rs_api = None

    consistency_level = None

    def __init__(self, migrated_check, alarm, consistency_level=None, alarm_cache=None):

        self.ck_api = migrated_check.ck_api
        self.rs_api = migrated_check.rs_api

        self.migrated_check = migrated_check

        self.consistency_level = consistency_level

        self._alarm_cache = alarm
        self.rs_alarm = self._find_alarm()

    def __str__(self):
        return '<Alarm: check_id=%s metadata=%s>' % (self._alarm_cache['check_id'], self._alarm_cache['metadata'])

    def _find_alarm(self):
        for alarm in self.migrated_check.migrated_entity.get_rs_alarms():

            if alarm.check_id != self._alarm_cache['check_id']:
                continue

            if alarm.notification_plan_id != self._alarm_cache['notification_plan_id']:
                continue

            if alarm.criteria != self._alarm_cache['criteria']:
                continue

            if alarm.extra != self._alarm_cache['metadata']:
                continue

            return alarm

    def test(self):
        valid, msg, results = self.migrated_check.get_test_results()
        if not valid:
            return False, 'Check test failed', msg

        # BUG: check results need moniitoring_zone_id and status for the alarm test to work, agent
        #      checks do not provide this.
        for r in results:
            if not r.get('monitoring_zone_id'):
                r['monitoring_zone_id'] = 'mzdfw'
            if not r.get('status'):
                r['status'] = 'dummy'

        alarm_result = self.rs_api.test_alarm(self.migrated_check.rs_entity, criteria=self._alarm_cache['criteria'], check_data=results)
        for r in alarm_result:
            if r['state'] != 'OK':
                return False, 'Alarm test failed', pprint.pformat(alarm_result)

        return True, 'Alarm test successful', pprint.pformat(alarm_result)

    def save(self, commit=True):
        if not self.rs_alarm:
            if commit:
                self.rs_alarm = self.rs_api.create_alarm(self.migrated_check.rs_entity, **self._alarm_cache)
            return 'Created', self._alarm_cache

        alarm = copy(self._alarm_cache)

        if alarm['metadata'] == self.rs_alarm.extra:
            alarm.pop('metadata')

        for key in ['check_id', 'notification_plan_id', 'criteria']:
            if alarm.get(key) == getattr(self.rs_alarm, key, None):
                try:
                    alarm.pop(key)
                except KeyError:
                    pass

        if alarm:
            if commit:
                self.rs_alarm = self.rs_api.update_alarm(self.rs_alarm, alarm)
            return 'Updated', alarm

        return 'Unchanged', None

    @classmethod
    def create_from_migrated_check(cls, migrated_check):
        alarms = translate(migrated_check)
        return [cls(migrated_check, alarm) for alarm in alarms]


class AlarmMigrator(object):

    def __init__(self, migrator, consistency_level=None, auto=False, dry_run=False, no_test=False, logger=None):

        self.logger = logger
        if not self.logger:
            self.logger = logging.getLogger('maas_migration')

        self.migrator = migrator
        self.ck_api = self.migrator.ck_api
        self.rs_api = self.migrator.rs_api

        self.dry_run = self.migrator.options.dry_run
        self.auto = self.migrator.options.auto
        self.no_test = self.migrator.options.no_test

        self.consistency_level = self.migrator.config.get('alarm_consistency_level', 'ALL')

    def migrate(self):
        self.logger.info('\nAlarms')
        self.logger.info('------\n')
        self.logger.info('NOTE: You must have at least one active notification endpoint applied to the')
        self.logger.info('Cloudkick monitor or alarms will not be created. (You can do this in Cloudkick')
        self.logger.info('and re-run the script)\n')

        for migrated_entity in self.migrator.migrated_entities:
            for migrated_check in migrated_entity.migrated_checks:

                alarms = MigratedAlarm.create_from_migrated_check(migrated_check)

                self.logger.info('Node: %s' % migrated_check.ck_node)
                self.logger.info('Check: %s' % migrated_check.ck_check)

                if not alarms:
                    self.logger.info('No alarms to create')

                for alarm in alarms:
                    self.logger.info('Alarm: %s' % alarm)
                    self.logger.debug('Alarm Criteria:\n%s' % alarm._alarm_cache['criteria'])

                    action, result = alarm.save(commit=False)

                    if action in ['Created', 'Updated']:
                        if not self.no_test:
                            valid, msg, results = alarm.test()
                            self.logger.info(msg)
                            self.logger.debug('%s' % (results))
                            if not valid:
                                if utils.get_input('Ignore this alarm?', options=['y', 'n'], default='y') == 'y':
                                    continue

                        if self.auto or utils.get_input('Save this alarm?', options=['y', 'n'], default='y') == 'y':
                            action, _ = alarm.save()
                            self.logger('%s alarm %s' % (action, alarm.rs_alarm.id))

                    else:
                        self.logger.info('Found alarm %s' % alarm.rs_alarm.id)

                self.logger.info('')
