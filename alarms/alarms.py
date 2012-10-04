import pprint

from translator import translate

import utils
import logging
log = logging.getLogger('maas_migration')

_consistency_levels = ['ALL', 'ONE', 'QUORUM']


class Alarms(object):

    def __init__(self, cloudkick, rackspace, checks_map, notification_plans, consistency_level=None, auto=False, dry_run=False):
        self.cloudkick = cloudkick
        self.rackspace = rackspace
        self.checks_map = checks_map
        self.notification_plans = notification_plans

        self.dry_run = dry_run
        self.auto = auto

        self.consistency_level = consistency_level

    def _get_node_str(self, node):
        return '%s (%s) ips:%s' % (node.get('name'), node.get('id'), ','.join(node.get('public_ips', []) + node.get('private_ips', [])))

    def _get_entity_str(self, entity):
        return '%s (%s) ips:%s' % (entity.label, entity.id, ','.join([ip for _, ip in entity.ip_addresses]))

    def _alarm_eq(self, rs_alarm, alarm_dict):
        return all((rs_alarm.check_id == alarm_dict['check_id'],
                   rs_alarm.notification_plan_id == alarm_dict['notification_plan_id'],
                   rs_alarm.criteria == alarm_dict['criteria'],
                   rs_alarm.extra == alarm_dict['metadata']))

    def _is_duplicate_alarm(self, rs_alarm_list, alarm_dict):
        eq_list = map(lambda a: self._alarm_eq(a, alarm_dict), rs_alarm_list)
        return any(eq_list)

    def sync_alarms(self):
        log.info('\nAlarms')
        log.info('------\n')
        log.info('NOTE: You must have at least one active notification endpoint applied to the')
        log.info('Cloudkick monitor or alarms will not be created. (You can do this in Cloudkick')
        log.info('and re-run the script)')

        for node, entity, check, new_check, monitor in self.checks_map:

            rs_alarms = self.rackspace.list_alarms(entity)

            # The core assertion here is that you have to have at least one active notification endpoint
            # in cloudkick or we won't bother setting up alarms.
            alarms = translate(new_check, check, self.notification_plans.get(monitor['id']))

            log.info('Node:\n%s' % (self._get_entity_str(entity)))
            log.info('Check:\n%s' % (pprint.pformat(check)))

            if not alarms:
                log.info('No alarms to create')

            for alarm in alarms:
                log.debug('Alarm:\n%s' % pprint.pformat(alarm))
                if self._is_duplicate_alarm(rs_alarms, alarm):
                    log.info('No update needed')
                    continue

                # first, we have to run a test check and get the results
                check_result = None
                check_test_success = True
                try:
                    check_result = self.rackspace.test_existing_check(new_check)
                    if False in [r['available'] for r in check_result]:
                        check_test_success = False
                except Exception as e:
                    check_result = e
                    check_test_success = False
                if not check_test_success:
                    log.info('Check Test Results:\n%s' % pprint.pformat(check_result))
                    if utils.get_input('Check test failed - save alarm anyway?', options=['y', 'n'], default='n') != 'y':
                        continue

                # if the test check worked, we can test the alarm
                save_alarm = True
                if check_test_success:
                    # BUG: check results need moniitoring_zone_id and status for the alarm test to work, agent
                    #      checks do not provide this.
                    for r in check_result:
                        if not r.get('monitoring_zone_id'):
                            r['monitoring_zone_id'] = 'mzdfw'
                        if not r.get('status'):
                            r['status'] = 'dummy'

                    alarm_result = self.rackspace.test_alarm(entity, criteria=alarm['criteria'], check_data=check_result)
                    for r in alarm_result:
                        log.debug('Alarm Test Results:\n%s' % pprint.pformat(alarm_result))
                        if r['state'] != 'OK':
                            if utils.get_input('Alarm test failed - save alarm anyway?', options=['y', 'n'], default='n') != 'y':
                                save_alarm = False
                                break

                if save_alarm and (self.auto or utils.get_input('Save this alarm?', options=['y', 'n'], default='y') == 'y'):
                    self.rackspace.create_alarm(entity, **alarm)
                else:
                    log.info('skipping')

            log.info('')
