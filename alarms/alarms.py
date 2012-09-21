import pprint

from translator import translate

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
        print '\nAlarms'
        print '------\n'
        print 'NOTE: You must have at least one active notification endpoint applied to the'
        print 'Cloudkick monitor or alarms will not be created. (You can do this in the Cloudkick'
        print 'and re-run the script)'

        for node, entity, check, new_check, monitor in self.checks_map:
            rs_alarms = self.rackspace.list_alarms(entity)

            # The core assertion here is that you have to have at least one active notification endpoint
            # in cloudkick or we won't bother setting up alarms.
            alarms = translate(new_check, check, self.notification_plans.get(monitor['id']))

            if alarms:
                for alarm in alarms:
                    pprint.pprint(alarm)

                    if self._is_duplicate_alarm(rs_alarms, alarm):
                        print 'Duplicate alarm detected, skipping'
                        continue

                    try:
                        check_result = self.rackspace.test_existing_check(new_check)
                        if False in [r['available'] for r in check_result]:
                            print 'Check test failed for check %s, save alarm anyway?' % (new_check),
                            if not raw_input('[y/n]') == 'y':
                                continue
                    except Exception as e:
                        check_result = None
                        print 'Check test failed!'
                        print 'Exception: %s' % e
                        print 'Save alarm anyway?'
                        if not raw_input('[y/n]') == 'y':
                            continue

                    if check_result:
                        alarm_result = self.rackspace.test_alarm(entity, criteria=alarm['criteria'], check_data=check_result)[0]
                        if alarm_result['state'] != 'OK':
                            print 'Alarm test failed with result:\n%s' % alarm_result
                            print 'Save alarm anyway?',
                            if raw_input('[y/n]: ') != 'y':
                                continue

                    try:
                        self.rackspace.create_alarm(entity, **alarm)
                    except Exception as e:
                        import pdb; pdb.set_trace()

        print 'TODO'
