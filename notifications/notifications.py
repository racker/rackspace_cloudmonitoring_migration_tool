from collections import defaultdict
import pprint
import utils
import logging
log = logging.getLogger('maas_migration')


class Notifications(object):

    def __init__(self, cloudkick, rackspace, monitors, auto=False, dry_run=False):
        self.cloudkick = cloudkick
        self.rackspace = rackspace
        self.monitors = monitors

        self.dry_run = dry_run
        self.auto = auto

        self.plans = rackspace.list_notification_plans()
        self.notifications = dict((n.id, n) for n in rackspace.list_notifications())

    def _get_or_create_notification(self, new_notification):

        # find existing notifications
        for notification_id, notification in self.notifications.items():
            if notification.type == new_notification['type'] and \
               notification.details == new_notification['details']:
                return notification, False

        # create it if it doesn't exist
        log.info('Notification: %s' % new_notification['details']['address'])
        if self.auto or utils.get_input('Create notification?', options=['y', 'n'], default='y') == 'y':
            notification = self.rackspace.create_notification(**new_notification)
            self.notifications[notification.id] = notification
            return notification, True

        None, False

    def _generate_cloudkick_notification_plans(self):

        # look up notifications attached to cloudkick monitors
        ck = defaultdict(set)
        for monitor in self.monitors:
            ck_notifications = monitor.get('notification_receivers', [])
            for ck_notification in ck_notifications:
                if 'email_address' in ck_notification['details']:
                    ck[(monitor['id'], monitor['name'])].add((ck_notification['name'], 'email', ck_notification['details']['email_address']))
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
                new_notification['details']['address'] = details
                notification, created = self._get_or_create_notification(new_notification)
                if notification:
                    log.debug('%s notification: %s' % ('Created' if created else 'Found', new_notification['details']['address']))
                    created_notifications[monitor].append(notification)
                else:
                    log.debug('Skipped notification: %s' % new_notification['details']['address'])

        # create a plan per monitor
        plans = {}

        # find any existing plans for monitor.
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
                    log.info('Plan\n%s' % pprint.pformat(new_plan))
                    if self.auto or utils.get_input('Update plan?', options=['y', 'n'], default='y') == 'y':
                        plan = self.rackspace.update_notification_plan(old_plan, new_plan)
            else:
                log.info('Plan\n%s' % pprint.pformat(new_plan))
                if self.auto or utils.get_input('Create plan?', options=['y', 'n'], default='y') == 'y':
                    plan = self.rackspace.create_notification_plan(**new_plan)

            if plan:
                plans[monitor[0]] = plan

        return plans

    def sync_notifications(self):
        log.info('\nNotifications')
        log.info('------\n')

        plans = self._generate_cloudkick_notification_plans()

        return plans
