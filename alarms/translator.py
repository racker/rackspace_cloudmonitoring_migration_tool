import templates


def _make_alarm(label, rs_check, notification_plan, criteria):
    alarm = {}
    alarm['check_id'] = rs_check.id
    alarm['notification_plan_id'] = notification_plan.id
    alarm['metadata'] = rs_check.extra
    alarm['metadata']['check_type'] = label
    alarm['criteria'] = criteria
    return alarm


def translate_agent_plugin(rs_check, ck_check, notification_plan):
    criteria = templates.agent_plugin
    return _make_alarm('agent_plugin', rs_check, notification_plan, criteria)


def translate_http(rs_check, ck_check, notification_plan):
    criteria = ''

    if 'code' in ck_check.details:
        criteria += templates.http_status_code.format(status_code_regex=ck_check.details['code'])

    if 'body' in ck_check.details:
        # The regex is already applied in the Check, so the alarm
        # simply checks whether the match is an empty string
        criteria += templates.http_body_match.format(body_match=ck_check.details['body'])

    if 'rt_ms' in ck_check.details:
        criteria += templates.http_response_time.format(response_time=ck_check.details['rt_ms'])

    criteria += templates.http_ok

    return _make_alarm('http', rs_check, notification_plan, criteria)


def translate_ping(rs_check, ck_check, notification_plan):
    criteria = templates.ping_packet_loss.format()
    return _make_alarm('ping', rs_check, notification_plan, criteria)


def translate_ssh(rs_check, ck_check, notification_plan):
    criteria = templates.ssh_server_listening.format()
    return _make_alarm('ssh', rs_check, notification_plan, criteria)


def translate_dns(rs_check, ck_check, notification_plan):
    criteria = templates.dns_record_exists.format()
    return _make_alarm('dns', rs_check, notification_plan, criteria)


def translate_tcp(rs_check, ck_check, notification_plan):
    criteria = ''

    if 'banner_match' in ck_check.details:
        criteria += templates.tcp_banner_match.format(banner_match=ck_check.details['banner_match'])

    criteria += templates.tcp_connection_established.format()

    return _make_alarm('tcp', rs_check, notification_plan, criteria)


def translate_agent_memory(rs_check, ck_check, notification_plan):
    criteria = ""
    if 'mem_percent_crit' in ck_check.details:
        criteria = criteria + templates.memory_percent_critical.format(memory_percent_critical=ck_check.details['mem_percent_crit'])
    if 'mem_percent_warn' in ck_check.details:
        criteria = criteria + templates.memory_percent_warning.format(memory_percent_warning=ck_check.details['mem_percent_warn'])
    if 'mem_percent_crit' in ck_check.details or 'mem_percent_warn' in ck_check.details:
        criteria = criteria + templates.memory_percent_ok.format()
    if criteria:
        return _make_alarm('memory_percent_used', rs_check, notification_plan, criteria)


def translate_agent_filesystem(rs_check, ck_check, notification_plan):
    criteria = ""
    if 'fs_critical' in ck_check.details:
        criteria = criteria + templates.disk_percent_critical.format(disk_percent_critical=ck_check.details['fs_critical'])
    if 'fs_warn' in ck_check.details:
        criteria = criteria + templates.disk_percent_warning.format(disk_percent_warning=ck_check.details['fs_warn'])
    if 'fs_critical' in ck_check.details or 'fs_warn' in ck_check.details:
        criteria = criteria + templates.disk_percent_ok.format()
    if criteria:
        return _make_alarm('disk_percent_used', rs_check, notification_plan, criteria)

_map = {
    'remote.http': translate_http,
    'remote.ping': translate_ping,
    'remote.ssh': translate_ssh,
    'remote.dns': translate_dns,
    'remote.tcp': translate_tcp,
    'agent.memory': translate_agent_memory,
    'agent.plugin': translate_agent_plugin,
    'agent.filesystem': translate_agent_filesystem
}


def translate(migrated_check, **kwargs):
    if not migrated_check.rs_notification_plan:
        return None

    f = _map.get(migrated_check.rs_check.type)
    if f:
        return f(migrated_check.rs_check, migrated_check.ck_check, migrated_check.rs_notification_plan, **kwargs)
    else:
        return None
