# Configuration instructions

Copy config.json.dist to config.json and set these configation settings:

* **cloudkick_oauth_key**: OAuth key for Cloudkick account; Must have read priveliges.
* **cloudkick_oauth_secret**: OAuth secret for Cloudkick account.
* **rackspace_username**: Username for a Rackspace account.
* **rackspace_apikey**: API key for a Rackspace account.
* **ca_certs_path**: Path to a CAcert root certificate bundle.  By default one is included as cacert.pem.

# Usage Instructions

## Manual Mode

To run the migration script in manual mode (you are asked to confirm every action), run:
    
    ./migrate.py

## Automatic Mode

To run the migration script in automatic mode, run:

    ./migrate.py --auto
    
You will be asked to specify which monitoring zones you wish to use for migrated checks, but all other migration tasks will be accomplished automatically.

## Delete all MaaS data

To delete all MaaS resources, run:

    ./migrate.py clean