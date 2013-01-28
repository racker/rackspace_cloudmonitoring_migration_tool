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
    
## Delete all MaaS data

To delete **ALL** Rackspace cloud monitoring resources, run:

    ./migrate.py -c /path/to/config.json clean
