#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Scott Harney <scotth@scottharney.com>
#
# This file is a contribution to Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.


DOCUMENTATION = '''
---
module: netapp-setup
version_added: 0.1
short_description: NetApp Clustered Data OnTap facts module
description:
   - This module populates facts about NetApp Clustered Data OnTap systems
author: Scott Harney
'''

import logging
import sys
import xmltodict # pip install xmltodict src: https://github.com/martinblech/xmltodict
sys.path.append("/home/sharney/source/ansible-netapp/library/NetApp") 
from NaServer import * # NetApp Managability SDK symlink or copy ./NetApp/lib/python/* in ./library

EXAMPLES = '''
ansible -M ./library -t /tmp/facts -c local -m netapp-setup -i vars/hosts 192.169.2.13 -a "host={{ inventory_hostname }}  nauser=admin napass=mypass"

ansible-playbook -M library -i vars/otherhosts playbooks/test_facts.yml
'''

def netapp_info(module) :
   
    results = {}

    #This module is not built to make changes, so we are returning false here.
    results['changed'] = False
    results['rc'] = 0
    results['ansible_facts'] = {}

    s = NaServer(module.params['host'], 1 , 21)
    s.set_server_type(module.params['na_server_type'])
    s.set_transport_type(module.params['na_transport_type'])
    s.set_port(module.params['na_port'])
    s.set_style(module.params['na_style'])
    s.set_admin_user(module.params['nauser'], module.params['napass'])

    # first we get base cluster OnTap version information
    cluster_version_info = {}
    api = NaElement("system-get-version")
    xo = s.invoke_elem(api)
    if (xo.results_status() == "failed") :
        errmsg = "errno: ", xo.results_errno(), "reason: ", xo.results_reason()
        module.fail_json(msg=errmsg)
    
    cluster_version = {}
    cluster_version['build_timestamp'] = xo.child_get_string('build-timestamp')
    cluster_version['is_clustered'] = xo.child_get_string('is-clustered')
    cluster_version['version'] = xo.child_get_string('version')
    cluster_version['version_tuple'] = xmltodict.parse(xo.child_get('version-tuple').sprintf())
    cluster_version_info['cluster_version_info'] = cluster_version
    #o = xmltodict.parse(xo.sprintf())
    results['ansible_facts'].update(cluster_version_info)

    # cluster identity info
    cluster_identity_info = {}
    api = NaElement("cluster-identity-get")
    xo = s.invoke_elem(api)
    if (xo.results_status() == "failed") :
        errmsg = "errno: ", xo.results_errno(), "reason: ", xo.results_reason()
        module.fail_json(msg=errmsg)
    
    cluster_identity = {}
    attr = xo.child_get('attributes') 
    id_info = attr.child_get('cluster-identity-info')
    for cid in id_info.children_get() :
        cluster_name = id_info.child_get_string('cluster-name')
        cluster_identity[cluster_name] = xmltodict.parse(id_info.sprintf())
        
    cluster_identity_info['cluster_identity'] = cluster_identity
    results['ansible_facts'].update(cluster_identity_info)


    # get node specific info
    system_node_info = {}
    system_info = {}
    api = NaElement("system-get-node-info-iter")
    xo = s.invoke_elem(api)
    if (xo.results_status() == "failed") :
        errmsg = "errno: ", xo.results_errno(), "reason: ", xo.results_reason()
        module.fail_json(msg=errmsg)
        
    system_nodes = xo.child_get('attributes-list')
    for node in system_nodes.children_get() :
        system_name = node.child_get_string('system-name')
        system_info[system_name] = xmltodict.parse(node.sprintf())
        
    system_node_info['system_node_info'] = system_info
    results['ansible_facts'].update(system_node_info)

    # get svm info
    svm_info = {}
    vserver_info = {}
    api = NaElement("vserver-get-iter")
    xo = s.invoke_elem(api)
    if (xo.results_status() == "failed") :
        errmsg = "errno: ", xo.results_errno(), "reason: ", xo.results_reason()
        module.fail_json(msg=errmsg)
        
    vservers = xo.child_get('attributes-list')
    for vserver in vservers.children_get() :
        svm_name = vserver.child_get_string('vserver-name')
        vserver_info[svm_name] = xmltodict.parse(vserver.sprintf())
        
    svm_info['svm_info'] = vserver_info
    results['ansible_facts'].update(svm_info)
    
    # get aggr info
    aggr_info = {}
    aggregate_info = {}
    api = NaElement("aggr-get-iter")
    xo = s.invoke_elem(api)
    if (xo.results_status() == "failed") :
        errmsg = "errno: ", xo.results_errno(), "reason: ", xo.results_reason()
        module.fail_json(msg=errmsg)
        
    aggr_list = xo.child_get('attributes-list')
    for aggrs in aggr_list.children_get() :
        aggr_attrs = aggr_list.child_get('aggr-attributes')
        for aggr in aggr_attrs.children_get() :
            aggregate_name = aggrs.child_get_string('aggregate-name')
            aggregate_info[aggregate_name] = xmltodict.parse(aggrs.sprintf())
            
    aggr_info['aggr_info'] = aggregate_info
            
    results['ansible_facts'].update(aggr_info)


    return results

### ---------------------------------------------------------------------------
### MAIN
### ---------------------------------------------------------------------------

def main():
  module = AnsibleModule(
    argument_spec = dict(
        host=dict(required=True),
        nauser=dict(required=True),
        napass=dict(required=True),
        na_server_type=dict(required=False, default="FILER"),
        na_transport_type=dict(required=False, default="HTTP"),
        na_port=dict(required=False, default=80),
        na_style=dict(required=False, default="LOGIN"),
        logfile=dict(required=False, default=None),
        timeout=dict(required=False, default=0)
    ),
    supports_check_mode = False
  )

  logfile = module.params.get('logfile')
  if logfile is not None:
    logging.basicConfig(filename=logfile, level=logging.INFO,
      format='%(asctime)s:%(name)s:%(message)s')
    logging.getLogger().name = 'CONFIG:'+ module.params['host']  

  logging.info("About to push configuration to host: {}".format(module.params['host']))
  results = netapp_info(module)

  module.exit_json(**results)

from ansible.module_utils.basic import *

from ansible.module_utils.facts import *

main()
