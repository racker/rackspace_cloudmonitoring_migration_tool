from collections import defaultdict
import pprint


class Notifications(object):

    def __init__(self, cloudkick, rackspace, monitors, auto=False, dry_run=False):
        self.cloudkick = cloudkick
        self.rackspace = rackspace
        self.monitors = monitors

        self.dry_run = dry_run
        self.auto = auto

        self.ignored_notifications = []
        self.plans = rackspace.list_notification_plans()
        self.notifications = dict((n.id, n) for n in rackspace.list_notifications())

    def _get_node_str(self, node):
        return '%s (%s) ips:%s' % (node.get('name'), node.get('id'), ','.join(node.get('public_ips', []) + node.get('private_ips', [])))

    def _get_entity_str(self, entity):
        return '%s (%s) ips:%s' % (entity.label, entity.id, ','.join([ip for _, ip in entity.ip_addresses]))

    def _get_notification_str(self, notification):
        return '%s (%s) %s:%s' % (notification.label, notification.id, notification.type, notification.details)

    def _get_plan_str(self, plan):
        rv = ''
        rv += 'Plan %s (%s)\n' % (plan.label, plan.id)
        rv += 'Critical State:\n%s\n' % ('\n'.join([self._get_notification_str(self.notifications[n]) for n in plan.critical_state]))
        rv += 'Warning State:\n%s\n' % ('\n'.join([self._get_notification_str(self.notifications[n]) for n in plan.warning_state]))
        rv += 'OK State:\n%s\n' % ('\n'.join([self._get_notification_str(self.notifications[n]) for n in plan.ok_state]))
        return rv

    def _get_or_create_notification(self, new_notification):
        for notification_id, notification in self.notifications.items():
            if notification.type == new_notification['type'] and \
               notification.details == new_notification['details']:
                return notification

        for notification_type, notification_details in self.ignored_notifications:
            if new_notification['type'] == notification_type and \
               new_notification['details'] == notification_details:
                return None

        print 'Notification: %s' % (new_notification)

        # test webhooks
        if new_notification['type'] == 'webhook':
            result = self.rackspace.test_notification(**new_notification)
            if not result['status'] == 'success':
                if not raw_input('Notification test failed, save anyway? [y/n] ') == 'y':
                    self.ignored_notifications.append((new_notification['type'], new_notification['details']))
                    return None

        if self.auto or raw_input('Create notification? [y/n] ') == 'y':
            notification = self.rackspace.create_notification(**new_notification)
            self.notifications[notification.id] = notification
            return notification
        else:
            self.ignored_notifications.append((new_notification['type'], new_notification['details']))
            return None

    def _generate_cloudkick_notification_plans(self):

        # look up notifications attached to cloudkick monitors
        ck = defaultdict(set)
        for monitor in self.monitors:
            ck_notifications = monitor.get('notification_receivers', [])
            for ck_notification in ck_notifications:
                if 'email_address' in ck_notification['details']:
                    ck[(monitor['id'], monitor['name'])].add((ck_notification['name'], 'email', ck_notification['details']['email_address']))
                elif 'url' in ck_notification['details']:
                    ck[(monitor['id'], monitor['name'])].add((ck_notification['name'], 'webhook', ck_notification['details']['url']))
                else:
                    pass

        # create any missing notifications
        created_notifications = {}
        for monitor, notifications in ck.items():
            created_notifications[monitor] = []
            new_notification = {}
            for name, notification_type, details in notifications:
                new_notification['label'] = name
                new_notification['type'] = notification_type
                new_notification['details'] = {}
                new_notification['details']['address' if notification_type == 'email' else 'url'] = details
                notification = self._get_or_create_notification(new_notification)
                if notification:
                    created_notifications[monitor].append(notification)

        # create a plan per monitor with associated notifications
        plans = {}
        for monitor, notifications in created_notifications.items():
            old_plan = None
            for plan in self.plans:
                if plan.label == '%s:%s' % (monitor[1], monitor[0]):
                    old_plan = plan
                    break

            new_plan = {}
            new_plan['label'] = '%s:%s' % (monitor[1], monitor[0])
            new_plan['critical_state'] = [n.id for n in notifications]
            new_plan['warning_state'] = [n.id for n in notifications]
            new_plan['ok_state'] = [n.id for n in notifications]

            plan = None
            if old_plan:
                if old_plan.critical_state == new_plan['critical_state'] and \
                   old_plan.warning_state == new_plan['warning_state'] and \
                   old_plan.ok_state == new_plan['ok_state']:
                    plan = old_plan
                else:
                    print pprint.pformat(new_plan)
                    if self.auto or raw_input('Update plan? ') == 'y':
                        plan = self.rackspace.update_notification_plan(old_plan, new_plan)
            else:
                print pprint.pformat(new_plan)
                if self.auto or raw_input('Create plan? ') == 'y':
                    plan = self.rackspace.create_notification_plan(**new_plan)

            if plan:
                plans[monitor[0]] = plan

        return plans

    def sync_notifications(self):
        print '\nNotifications'
        print '------\n'

        plans = self._generate_cloudkick_notification_plans()

        print 'Created Plans:'
        for monitor_id, plan in plans.items():
            print 'Monitor: %s' % monitor_id
            print self._get_plan_str(plan)

        return plans
