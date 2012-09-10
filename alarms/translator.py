import templates

def _make_alarm(label, rs_check, notification_plan, criteria):
    alarm = {}
    alarm['check_id'] = rs_check.id
    alarm['notification_plan_id'] = notification_plan.id
    alarm['label'] = label
    alarm['metadata'] = rs_check.extra
    alarm['metadata']['check_type'] = label
    alarm['criteria'] = criteria
    return alarm


def translate_http(rs_check, ck_check, notification_plan):
    alarms = []

    if 'code' in ck_check['details']:
        criteria = templates.http_status_code.format(status_code_regex=ck_check['details']['code'])
        alarms.append(_make_alarm('http_status_code', rs_check, notification_plan, criteria))

    if 'body' in ck_check['details']:
        # The regex is already applied in the Check, so the alarm
        # simply checks whether the match is an empty string
        criteria = templates.http_body_match.format(body_match=ck_check['details']['body'])
        alarms.append(_make_alarm('http_body_match', rs_check, notification_plan, criteria))

    if 'rt_ms' in ck_check['details']:
        criteria = templates.http_response_time.format(response_time=ck_check['details']['rt_ms'])
        alarms.append(_make_alarm('http_response_time', rs_check, notification_plan, criteria))

    return alarms


def translate_ping(rs_check, ck_check, notification_plan):
    alarms = []
    criteria = templates.ping_packet_loss.format()
    alarms.append(_make_alarm('ping_packet_loss', rs_check, notification_plan, criteria))

    return alarms

def translate_ssh(rs_check, ck_check, notification_plan):
    alarms = []
    criteria = templates.ssh_server_listening.format()
    alarms.append(_make_alarm('ssh_server_listening', rs_check, notification_plan, criteria))

    return alarms


def translate_dns(rs_check, ck_check, notification_plan):
    alarms = []
    criteria = templates.dns_record_exists.format()
    alarms.append(_make_alarm('dns_record_exists', rs_check, notification_plan, criteria))

    return alarms


def translate_tcp(rs_check, ck_check, notification_plan):
    alarms = []

    criteria = templates.tcp_connection_established.format()
    alarms.append(_make_alarm('tcp_connection_established', rs_check, notification_plan, criteria))

    if 'banner_match' in ck_check['details']:
        criteria = templates.tcp_banner_match.format(banner_match=ck_check['details']['banner_match'])
        alarms.append(_make_alarm('tcp_banner_match', rs_check, notification_plan, criteria))

    return alarms

def translate_agent_memory(rs_check, ck_check, notification_plan):
    alarms = []

    # Generate CPU stolen alarm
    criteria = ""
    if 'mem_percent_crit' in ck_check['details']:
        criteria = criteria + templates.memory_percent_critical.format(memory_percent_critical=ck_check['details']['mem_percent_crit'])
    if 'mem_percent_warn' in ck_check['details']:
        criteria = criteria + templates.memory_percent_warning.format(memory_percent_warning=ck_check['details']['mem_percent_warn'])
    if 'mem_percent_crit' in ck_check['details'] or 'mem_percent_warn' in ck_check['details']:
        criteria = criteria + templates.memory_percent_ok.format()
    if criteria:
        alarms.append(_make_alarm('memory_percent_used', rs_check, notification_plan, criteria))

    return alarms


_map = {
    'remote.http': translate_http,
    'remote.ping': translate_ping,
    'remote.ssh': translate_ssh,
    'remote.dns': translate_dns,
    'remote.tcp': translate_tcp,
    #'agent.disk': translate_agent_disk,
    #'agent.cpu': translate_agent_cpu,
    'agent.memory': translate_agent_memory,
    #'agent.plugin': translate_agent_plugin,
    #'agent.network': translate_agent_network
}


def translate(rs_check, ck_check, notification_plan, **kwargs):
    f = _map.get(rs_check.type)
    if f:
        return f(rs_check, ck_check, notification_plan, **kwargs)
    else:
        print 'Translator for check type %s not found' % (rs_check.type)
        return None
