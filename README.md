# \*\*Before proceeding, we strongly suggest that you read the [Cloud Monitoring Migration Guide](/racker/rackspace_cloudmonitoring_migration_tool/blob/master/docs/MIGRATION.md).**


# Configuration instructions

Copy config.json.dist to config.json and set these configation settings:

### Required
* **cloudkick_oauth_key**: OAuth key for Cloudkick account; Must have read priveliges.
* **cloudkick_oauth_secret**: OAuth secret for Cloudkick account.
* **rackspace_username**: Username for a Rackspace account.
* **rackspace_apikey**: API key for a Rackspace account.

### Optional
* **monitoring_zones**: List of monitoring zones you want to apply remote checks to (default: ['mzord', 'mzdfw', 'mzlon'])

# Usage Instructions

## Manual Mode

To run the migration script in manual mode (you are asked to confirm every action), run:
    
    ./migrate.py -c /path/to/config.json migrate

## Automatic Mode

To run the migration script in automatic mode (You are only prompted if a check or alarm test fails), run:

    ./migrate.py -c /path/to/config.json --auto migrate

## Really Automatic Mode

To migrate all Entities, Checks, Notification Endpoints, and Alarms automatically and without testing, run:

    ./migrate.py -c /path/to/config.json --auto --no-test migrate
    
## Delete all Rackspace cloud monitoring data

To delete **ALL** Rackspace cloud monitoring resources, run:

    ./migrate.py -c /path/to/config.json clean

# Information and Caveats

### Entity IP Addresses

Nodes in Cloudkick are assigned a primary IPv4 address, which is the forced target of all external checks (HTTP, SSH, etc).

There are no such limitation in Rackspace Cloud Monitoring. IPv4 and IPv6 addresses can be assigned to entities and targeted by any combination of checks.

This tool will copy Cloudkick behavior, and target all external checks to the node's primary IPv4 address. 

### Agents and agent\_id

Rackspace Cloud Monitoring agents are explicity associated with an entity via the agent\_id attribute. It does not automatically happen as it did with Cloudkick agents.

If you want to be able to test migrated agent Checks with this tool, you'll need to set the agent up beforehand.

By default, this script will assume that the agent\_id is the *name of the node in Cloudkick*.

### Custom Plugins

The Cloudkick custom plugin output format is compatible with the Rackspace Cloud Monitoring Agent. 

You may simply copy your Cloudkick agent custom plugins directory to the Rackspace Cloud Monitoring agent plugins directory and this tool will properly migrate the check and set up an alarm.

### Migrated Objects

#### Nodes -> Entities

* Cloudkick nodes map directly to Rackspace Cloud Monitoring entities.
* This tool will associate a node to an existing entity if the IP addresses match.

#### Check -> Check

* Cloudkick checks map directly to Rackspace Cloud Monitorng checks, with an important difference: Cloudkick checks also set thresholds for alerts, where Rackspace checks simply collect the metrics.
* Thus, an associated Rackspace alarm will be automatically generated where applicable.

#### Notifications

* Rackspace Cloud Monitoring only supports 2 types of notifications - email and webhook.
* This tool will only migrate email notifications.

### Migrated Check Types

The following check types are migrated automatically by this tool:
        
* HTTP
* HTTPS
* PING
* SSH
* DNS
* TCP
* DISK
* CPU
* MEMORY
* PLUGIN
* BANDWIDTH
* LOADAVG

The following check types are supported in Rackspace Cloud Monitoring, but could not be automatically migrated:

* IO

The following check types are not supported in Rackspace Cloud Monitoring and will not be migrated and should be replaced with a custom plugin:

* MONGODB\_CONNECTIONS
* MONGODB\_INDEXCOUNTERS
* MONGODB\_MEMORY
* MONGODB\_OPCOUNTERS
* MONGODB\_ASSERTS
* APACHE
* VMWARE\_GUEST
* MEMCACHED
* JMX
* CASSANDRA\_CFSTATS
* CASSANDRA\_TPSTATS
* AGENT\_CONNECTED
* MYSQL
* REDIS
* HTTP\_PUSH
* HTTP\_JSON
* NGINX
