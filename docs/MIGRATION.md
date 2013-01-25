# Cloud Monitoring Migration Guide

As you migrate from Cloudkick to Cloud Monitoring, it is important to understand the differences between their architectures.  The purpose of this guide is to explain some of those differences, and introduce tools that will ease the transition process.

A more thorough description of these changes, and the motivation behind them may be found in a recent blog post.

## Cloudkick Architecture

In Cloudkick, checks were applied to nodes by using tag-based monitors--each monitor defined a set of checks to perform on the set of nodes that matched a specified query.  These nodes were automatically synchronized from various cloud providers using credentials supplied to Cloudkick.

This system had several advantages: it automated the process of adding and removing nodes as they became active or were destroyed, it simplified the process of monitoring a new node in an appropriate manner, and it allowed users to change the monitoring configuration of large sets of nodes in a single step.  Unfortunately, as the complexity of the system grew, we found that these features caused significant reliability problems.
      
## Cloud Monitoring Architecture

In contrast, Cloud Monitoring employs a much simpler model in which entities and checks form a hierarchy.  Every check is a direct attribute of a single entity, and checks are not applied using automated queries.  Each check is configured to run at a specific time interval, from a configurable set of monitoring zones, ensuring that your servers are monitored even in the event of Rackspace datacenter failure.  These data are then used to generate alerts, based upon a Javascript-like domain specific alarm language.

Given the lack of entity syncing, and automatic check application in Cloud Monitoring, some effort will be required on your part to keep your monitoring configuration in sync with the current state of your infrastructure.  Although this may be inconvenient, we feel that the reliability and scalability benefits of Cloud Monitoring outweigh these concerns, especially given that most users with large monitoring setups already use configuration management software.  We provide open source Chef recipes which you can use to automatically configure Cloud Monitoring.  Furthermore, given the simple REST API provided by Cloud Monitoring, integration into other configuration management systems should be possible.
      
## Migration Tools

### Monitoring GUI

Currently, Cloud Monitoring lacks visualization tools.  Although you can retrieve monitoring data and graph it yourself, this is inconvenient and not easily automated. In the interim--as more robust graphing tools are being developed--we created a lightweight and open source monitoring GUI, that graphs your monitoring data and supports saved graphs.  We provide a hosted version of this project, or you may download and host it yourself  

###Migration Script

An open source Cloudkick → Cloud Monitoring migration script has been developed to assist the migration process.  This Python script translates your Cloudkick monitoring setup--so far as features are supported--into equivalent Cloud Monitoring entities, checks, alarms, and notification plans.  More documentation is available in the README.

Although this script can be used to keep your Cloud Monitoring setup in sync with your Cloudkick setup, it does not represent a long-term solution to managing your monitoring infrastructure. Instead, it is offered to help you quickly experiment with Cloud Monitoring as you consider your transition; For long term use, we strongly recommend the use of configuration management system. For example, we provide a Chef cookbook that integrates with Cloud Monitoring:

### Chef Cookbook

We have developed an open source chef cookbook for using Cloud Monitoring; Documentation is available in the README.  If you discover bugs, or incomplete information, please file a Github issue and we will look into them!

## Appendix: Feature Comparison

A high level comparison between Cloudkick and Cloud Monitoring is provided below:

### Basic Features

<table>
<tr><th>Feature</th><th>Cloudkick</th><th>Cloud Monitoring</th></tr>
<tr>
      <td>Entity creation</td>
      <td>Automatic entity syncing across multiple cloud providers.  Manual entity creation also supported.</td>
      <td>Automatically syncing of Rackspace legacy and next-gen Cloud Servers.  Manual entity creation also supported.</td>
</tr>
<tr>
      <td>Tagging</td>
      <td>Tags may be applied to any entity.</td>
      <td>Not yet supported.</td>
</tr>
<tr>
      <td>Check application</td>
      <td>Manually, or automatically from tag-based queries.</td>
      <td>Manual application only</td>
</tr>
<tr>
      <td>Alarm language</td>
      <td>Not supported</td>
      <td>Alerts triggered using a domain-specific language that supports:
            <ul>
                  <li>Flow control (if statements)</li>
                  <li>Binary comparison operations</li>
                  <li>Regular expressions</li>
                  <li>Access to previous metric state</li>
            </ul>
            The language is not Turing-complete, and does not support:
            <ul>
                  <li>Persistent state</li>
                  <li>Looping</li>
            </ul>
      </td>
</tr>
<tr>
      <td>Notification types</td>
      <td>
            <ul>
                  <li>Email</li>
                  <li>SMS</li>
                  <li>Webhook</li>
                  <li>PagerDuty</li>
            </ul>
</td>
      <td>
            <ul>
                  <li>Email</li>
                  <li>Webhook</li>
            </ul>
      </td>
</tr>
<tr>
      <td>External Checks</td>
      <td>See the <a href="https://support.cloudkick.com/API/2.0/List_Check_Types">list of check types</a>.</td>
      <td>See the <a href="http://docs.rackspace.com/cm/api/v1.0/cm-devguide/content/appendix-check-types.html">list of available check types and fields</a>.</td>
</tr>
<tr>
      <td>Internal Checks</td>
      <td>Supported via an agent.  Also supports custom plugins.</td>
      <td>Supported via an agent.  Also supports custom plugins.  Agents connect to up to three monitoring zones to ensure fault-tolerance.</td>
</tr>

<tr>
      <td>Billing</td>
      <td>Plan-based billing, based upon number of monitored servers.</td>
      <td>Billing per unit time based upon number of active checks, and number of monitoring zones</td>
</tr>
</table>

### Integration

<table>
<tr><th>Feature</th><th>Cloudkick</th><th>Cloud Monitoring</th></tr>
<tr>
      <td>GUI</td>
      <td>Interactive web application.</td>
      <td>Partial integration into Next-Gen Control Panel</td>
</tr>
<tr>
      <td>API</td>
      <td>
            <ul>
                  <li>API v1.0: (no docs)</li>
                  <li>API v2.0: <a href="https://support.cloudkick.com/API/2.0">docs</a></li>
            </ul>
      </td>
      <td>
            <ul>
                  <li>REST API v1.0: <a href="http://docs.rackspace.com/cm/api/v1.0/cm-devguide/content/overview.html"docs</a></li>
            </ul>
      </td>
</tr>
<tr>
      <td>Tools and Integration</td>
      <td>
            <ul>
                  <li>Python library: <a href="https://github.com/cloudkick/cloudkick-py"cloudkick-py</a></li>
                  <li>Command-line: <a href="https://github.com/cloudkick/cloudkick-cli"cloudkick-cli</a></li>
            </ul>
      </td>
      <td>
            <ul>
                  <li>Python library: <a href="https://github.com/racker/rackspace-monitoring-cli">rackspace-monitoring</a></li>
                  <li>Command-line: <a href="https://github.com/racker/rackspace-monitoring-cli">rackspace-monitoring-cli</a></li>
                  <li>Chef cookbook: <a href="https://github.com/racker/cookbook-cloudmonitoring">cloud monitoring chef cookbook</a></li>
            </ul>
      </td>
</tr>
<tr>
      <td>Visualization</td>
      <td>Graphing of metric data via Saved Graphs and Aggregate Graphs.</td>
      <td>Not yet supported.  Interim support via <a href="https://github.com/racker/rackspace-monitoring-gui">rackspace-monitoring-gui</a>.</td>
</tr>
<tr>
      <td>Website authentication</td>
      <td>
            <ul>
                  <li>Username + password</li>
                  <li>Two-factor authentication (optional)</li>
            </ul>
      </td>
      <td>
            <ul>
                  <li>Username + password</li>
            </ul>
      </td>
</tr>
<tr>
      <td>API authentication</td>
      <td>
            <ul>
                  <li>OAuth</li>
            </ul>
      </td>
      <td>
            <ul>
                  <li>Username + API key, then auth token.</li>
            </ul>
      </td>
</tr>
<tr>
      <td>User permissions</td>
      <td>
            <ul>
                  <li>Multiple user access to account</li>
                  <li>Role-based permissions</li>
                  <li>Configurable API key permissions</li>
            </ul>
      </td>
      <td>Not supported</td>
</tr>
<tr>
      <td></td>
      <td></td>
      <td></td>
</tr>
</table>

            <ul>
                  <li></li>
            </ul>
