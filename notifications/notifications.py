import pprint
import utils
import logging
from collections import defaultdict


class NotificationMigrator(object):

    def __init__(self, migrator, logger=None):
        self.logger = logger
        if not self.logger:
            self.logger = logging.getLogger('maas_migration')

        self.migrator = migrator
        self.ck_api = self.migrator.ck_api
        self.rs_api = self.migrator.rs_api

        self.dry_run = self.migrator.options.dry_run
        self.auto = self.migrator.options.auto

        self.rs_plans = self.rs_api.list_notification_plans()
        self.rs_notifications = dict((n.id, n) for n in self.rs_api.list_notifications())

        self.migrated_notifications = {}
        self.monitor_to_notification_map = defaultdict(set)

    def _get_or_create_notification(self, ck_notification):
        """
        Actually finds/creates a new rackspace notification
        """

        if ck_notification.address in self.migrated_notifications:
            return self.migrated_notifications[ck_notification.address]

        new_notification = {}
        new_notification['label'] = ck_notification.name
        new_notification['type'] = ck_notification.type
        new_notification['details'] = {}
        new_notification['details']['address'] = ck_notification.address

        # find existing notifications
        created = False
        notification = None
        for notification_id, rs_notification in self.rs_notifications.items():
            if rs_notification.type == new_notification['type'] and rs_notification.details == new_notification['details']:
                notification = rs_notification
                break

        # create it if it doesn't exist
        if not notification:
            if self.auto or utils.get_input('Create notification?', options=['y', 'n'], default='y') == 'y':
                rs_notification = self.rs_api.create_notification(**new_notification)
                notification = rs_notification
                created = True

        self.logger.info('%s Notification: %s (%s)' % ('Created' if created else 'Found', notification.details['address'], notification.id))
        return notification

    def _generate_notifications(self, ck_monitor):
        """
        Iterates over all notifications in a monitor, finds/creates them, and adds them to a map for later use
        """
        for ck_notification in ck_monitor.get_notifications():
            rs_notificaiton = self._get_or_create_notification(ck_notification)
            if rs_notificaiton:
                # We only need 1 notification per email address
                self.migrated_notifications[ck_notification.address] = rs_notificaiton

                # Map this notification to the monitor
                found = False
                for notificaion in self.monitor_to_notification_map[ck_monitor.id]:
                    if notificaion.details['address'] == rs_notificaiton.details['address']:
                        found = True
                        break
                if not found:
                    self.monitor_to_notification_map[ck_monitor.id].add(rs_notificaiton)

    def _generate_plan(self, ck_monitor):
        """
        Generates a plan for each monitor
        """

        notifications = self.monitor_to_notification_map.get(ck_monitor.id, [])
        new_plan = {}
        new_plan['label'] = '%s:%s' % (ck_monitor.name, ck_monitor.id)
        new_plan['critical_state'] = [n.id for n in notifications]
        new_plan['warning_state'] = [n.id for n in notifications]
        new_plan['ok_state'] = [n.id for n in notifications]

        # find already created plan
        action = ''
        plan = None
        for p in self.rs_plans:
            if p.label == '%s:%s' % (ck_monitor.name, ck_monitor.id):
                plan = p
                break

        if plan:
            if plan.critical_state == new_plan['critical_state'] and \
               plan.warning_state == new_plan['warning_state'] and \
               plan.ok_state == new_plan['ok_state']:
                action = 'Found'
            else:
                plan = self.rs_api.update_notification_plan(plan, new_plan)
                action = 'Updated'
        else:
            plan = self.rs_api.create_notification_plan(**new_plan)
            action = 'Created'

        self.logger.info('%s Plan %s:\n%s' % (action, plan.id, pprint.pformat(new_plan)))
        return plan

    def _monitors(self):
        monitors = {}
        for migrated_entity in self.migrator.migrated_entities:
            for migrated_check in migrated_entity.migrated_checks:
                monitors[migrated_check.ck_check.monitor.id] = migrated_check.ck_check.monitor
        return monitors.values()

    def _apply_plan(self, monitor, plan):
        """
        Set this plan as an attribute on all relevant migrate_check instances
        """
        for entity in self.migrator.migrated_entities:
            for check in entity.migrated_checks:
                if check.ck_check.monitor.id == monitor.id:
                    check.rs_notification_plan = plan

    def migrate(self):
        """
        1. find monitors with actually migrated checks
        2. find/create relevant notification endpoints
        3. find/create a plan with relevant endpoints for each monitor
        4. set plan as an attribute on each check for later use

        The result of this is a single notification endpoint per unique
        email address and 1 plan per monitor. (In Cloudkick, a monitor is
        a parent container for many checks)
        """
        self.logger.info('\nNotifications')
        self.logger.info('------\n')

        for monitor in self._monitors():
            self._generate_notifications(monitor)
            self.logger.info('')
            plan = self._generate_plan(monitor)
            if plan:
                self._apply_plan(monitor, plan)
