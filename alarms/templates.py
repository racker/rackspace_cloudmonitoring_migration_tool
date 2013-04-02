"""
Alarm templates
"""

# Agent Plugins
agent_plugin = \
"""
if (metric['legacy_state'] == 'err') {
    return new AlarmStatus(CRITICAL);
}
if (metric['legacy_state'] == 'warn') {
    return new AlarmStatus(WARNING);
}
return new AlarmStatus(OK);
"""

# HTTP
http_status_code = \
"""
if (metric['code'] nregex '{status_code_regex}') {{
  return new AlarmStatus(CRITICAL, 'HTTP server did not respond with {status_code_regex} status');
}}
"""
http_body_match = \
"""
if (metric['body_match'] == '') {{
    return new AlarmStatus(CRITICAL, 'HTTP response did not match {body_match}');
}}
"""
http_response_time = \
"""
if (metric['duration'] >= {response_time}) {{
  return new AlarmStatus(CRITICAL, 'HTTP request took {response_time} or more milliseconds.');
}}
"""
http_ok = \
"""
return new AlarmStatus(OK);
"""

ping_packet_loss = \
"""
if (metric['available'] < 100) {{
  return new AlarmStatus(CRITICAL, 'Packet loss detected');
}}
return new AlarmStatus(OK, 'No packet loss detected');
"""

# A null alarm to associate the check with a nofitication plan.
# If TCP server is not listening, then a CRITICAL state is automatically applied.
tcp_banner_match = \
"""
if (metric['banner'] nregex '{banner_match}') {{
  return new AlarmStatus(CRITICAL, 'TCP banner did not match {banner_match}');
}}
"""
tcp_ok = \
"""
return new AlarmStatus(OK, 'TCP connection established succesfully');
"""

# A null alarm to associate the check with a nofitication plan.
# If SSH is not listening, then a CRITICAL state is automatically applied.
ssh_server_listening = \
"""
return new AlarmStatus(OK, 'SSH connection established succesfully');
"""

# A null alarm to associate the check with a nofitication plan.
# If the DNS record doesn't exists, then a CRITICAL state is automatically applied
dns_record_exists = \
"""
return new AlarmStatus(OK, 'DNS record exists');
"""

memory_percent_critical = \
"""
if (percentage(metric['used'], metric['total']) > {memory_percent_critical}) {{
  return new AlarmStatus(CRITICAL, 'Memory usage exceeded {memory_percent_critical}%');
}}
"""
memory_percent_warning = \
"""
if (percentage(metric['used'], metric['total']) > {memory_percent_warning}) {{
  return new AlarmStatus(WARNING, 'Memory usage exceeded {memory_percent_warning}%');
}}
"""
memory_percent_ok = \
"""
return new AlarmStatus(OK, 'Memory usage was normal');
"""

disk_percent_critical = \
"""
if (percentage(metric['used'], metric['total']) > {disk_percent_critical}) {{
  return new AlarmStatus(CRITICAL, 'Disk usage exceeded {disk_percent_critical}%');
}}
"""
disk_percent_warning = \
"""
if (percentage(metric['used'], metric['total']) > {disk_percent_warning}) {{
  return new AlarmStatus(WARNING, 'Disk usage exceeded {disk_percent_warning}%');
}}
"""
disk_percent_ok = \
"""
return new AlarmStatus(OK, 'Disk usage was normal');
"""
