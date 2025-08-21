#!/usr/bin/env python3

"""Manages the ExaBGP test peer for the live autograder."""

import os
import time
import re
import subprocess
from collections import defaultdict

from ctn_utils import client, exec_ctn, get_ctn_name_lst, remove_ctn
import mnet_utils as mnet

EXABGP_CTN_NAME = "AUTOGRADER_EXABGP_PEER"
EXABGP_CONF_LOCAL_PATH = os.path.join(os.getcwd(), "exabgp.conf")
EXABGP_LOG_LOCAL_PATH = os.path.join(os.getcwd(), "exabgp.log")
EXABGP_CONF_CTN_PATH = "/etc/exabgp/exabgp.conf"
EXABGP_LOG_CTN_PATH = "/var/log/exabgp.log"
EXABGP_ENV_CTN_PATH = "/etc/exabgp/exabgp.env"

def start_exabgp_container():
    """Starts a single, long-running ExaBGP container if not already running."""
    if EXABGP_CTN_NAME in get_ctn_name_lst(f"^{EXABGP_CTN_NAME}$"):
        print("ExaBGP container is already running.")
        return

    print("Starting ExaBGP container...")
    open(EXABGP_CONF_LOCAL_PATH, 'a').close()
    open(EXABGP_LOG_LOCAL_PATH, 'a').close()

    client.containers.run(
        image="yuchen14/d_exabgp",
        name=EXABGP_CTN_NAME,
        network_mode="none",
        privileged=True,
        detach=True,
        volumes={
            EXABGP_CONF_LOCAL_PATH: {"bind": EXABGP_CONF_CTN_PATH, "mode": "rw"},
            EXABGP_LOG_LOCAL_PATH: {"bind": EXABGP_LOG_CTN_PATH, "mode": "rw"},
            os.path.join(os.getcwd(), "configs/exabgp.env"): {"bind": EXABGP_ENV_CTN_PATH, "mode": "ro"}
        },
    )
    time.sleep(5)
    print(f"ExaBGP container {EXABGP_CTN_NAME} started.")

def configure_exabgp_for_as(asn):
    """Configures ExaBGP to peer with all border routers of a given AS."""
    print(f"Configuring ExaBGP to peer with AS {asn}...")
    
    # This script is used to create veth pairs between containers.
    connect_script = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utils', 'autograder-25', 'connect_shadow_as.sh'))

    # Get student's external connections to determine its IPs
    student_ext_conns = mnet.get_exp_ext_conn(asn)
    exabgp_conf_content = ""

    for nb_name, r_name in mnet.NB_CONN.items():
        # 1. Get neighbor details
        nb_asn, nb_r = mnet.get_nb_asn_r(asn, nb_name)
        
        # 2. Determine IPs for both ends of the link
        student_ip_with_prefix = student_ext_conns[r_name][0][3]
        student_ip = student_ip_with_prefix.split('/')[0]

        neighbor_ext_conns = mnet.get_exp_ext_conn(nb_asn)
        exabgp_ip = ""
        for conn in neighbor_ext_conns.get(nb_r, []):
            if conn[0] == asn and conn[1] == r_name:
                exabgp_ip_with_prefix = conn[3]
                exabgp_ip = exabgp_ip_with_prefix.split('/')[0]
                break
        if not exabgp_ip:
            print(f"  Could not find reverse connection for {nb_name} from AS {nb_asn}. Skipping.")
            continue

        # 3. Get container and interface names
        student_r_ctn = mnet.get_r_ctn_name(asn, r_name)
        intf_r_name, intf_exabgp_name = mnet.get_ext_intf_names(asn, nb_name)

        # 4. Create veth pair and configure IPs
        print(f"  Connecting {EXABGP_CTN_NAME} to {student_r_ctn} for neighbor {nb_name}")
        
        # Create veth pair
        cmd_link = ["sudo", "bash", connect_script, "add_link", EXABGP_CTN_NAME, intf_exabgp_name, student_r_ctn, intf_r_name]
        subprocess.run(cmd_link, check=True, capture_output=True)

        # Configure IP on ExaBGP side
        cmd_addr_exabgp = ["sudo", "bash", connect_script, "add_addr", EXABGP_CTN_NAME, exabgp_ip, intf_exabgp_name]
        subprocess.run(cmd_addr_exabgp, check=True, capture_output=True)

        # Configure IP on student router side
        cmd_addr_student = ["sudo", "bash", connect_script, "add_addr", student_r_ctn, student_ip, intf_r_name]
        subprocess.run(cmd_addr_student, check=True, capture_output=True)

        # 5. Generate ExaBGP configuration snippet
        nb_lo = mnet.get_exp_intf_ip("lo", nb_asn, nb_r)

        exabgp_conf_content += f"neighbor {student_ip} {{\n"
        exabgp_conf_content += f"    description '{nb_name}--{r_name}';\n"
        exabgp_conf_content += f"    router-id {nb_lo};\n"
        exabgp_conf_content += f"    local-address {exabgp_ip};\n"
        exabgp_conf_content += f"    local-as {nb_asn};\n"
        exabgp_conf_content += f"    peer-as {asn};\n"
        exabgp_conf_content += "    family {\n"
        exabgp_conf_content += "         ipv4 unicast;\n"
        exabgp_conf_content += "    }\n"
        if nb_asn not in mnet.IXP_ASNS:
            exabgp_conf_content += "    static {\n"
            exabgp_conf_content += f"         route {nb_asn}.0.0.0/8 next-hop self;\n"
            exabgp_conf_content += "    }\n"
        exabgp_conf_content += "}\n"

    # 6. Write config and reload ExaBGP
    with open(EXABGP_CONF_LOCAL_PATH, "w") as f:
        f.write(exabgp_conf_content)

    print("  Reloading ExaBGP configuration...")
    exec_ctn(EXABGP_CTN_NAME, ["exabgpcli shutdown"], shell="bash")
    time.sleep(1)
    exec_ctn(EXABGP_CTN_NAME, [f"exabgp -e {EXABGP_ENV_CTN_PATH} {EXABGP_CONF_CTN_PATH} &"], shell="bash")
    print(f"ExaBGP configured for AS {asn}.")


def clear_exabgp_config():
    """Clears the ExaBGP configuration."""
    exec_ctn(EXABGP_CTN_NAME, ["exabgpcli shutdown"], shell="bash")
    with open(EXABGP_CONF_LOCAL_PATH, "w") as f:
        f.write("")
    exec_ctn(EXABGP_CTN_NAME, [f"exabgp -e {EXABGP_ENV_CTN_PATH} {EXABGP_CONF_CTN_PATH} &"], shell="bash")
    print("Cleared ExaBGP configuration.")

def announce_exabgp_route(neighbor, prefix, next_hop, **kwargs):
    """Announces a route from the ExaBGP test peer."""
    ann = f"neighbor {neighbor} announce route {prefix} next-hop {next_hop}"
    if kwargs.get('as_path'):
        ann += f" as-path [ {' '.join(map(str, kwargs['as_path']))} ]"
    if kwargs.get('community'):
        ann += f" community [ {' '.join(kwargs['community'])} ]"
    if kwargs.get('med'):
        ann += f" med {kwargs['med']}"
    cmd = [f"exabgpcli {ann}"]
    exec_ctn(EXABGP_CTN_NAME, cmd, shell="bash")

def withdraw_exabgp_route(neighbor, prefix):
    """Withdraws a route from the ExaBGP test peer."""
    ann = f"neighbor {neighbor} withdraw route {prefix}"
    cmd = [f"exabgpcli {ann}"]
    exec_ctn(EXABGP_CTN_NAME, cmd, shell="bash")

def get_exabgp_rib_in():
    """Return and parse the result of `exabgpcli show adj-rib in extensive`."""
    rib_in = defaultdict(lambda: defaultdict(dict))
    cmd = ["exabgpcli show adj-rib in extensive"]
    output = exec_ctn(EXABGP_CTN_NAME, cmd, shell="bash").strip().split("\n")
    if output == ['']:
        return rib_in
    for entry in output:
        neighbor_match = re.search(r"neighbor (\S+)", entry)
        if not neighbor_match: continue
        neighbor = neighbor_match.group(1)

        route_match = re.search(r"ipv4 unicast (\S+)", entry)
        if not route_match: continue
        route = route_match.group(1)

        next_hop_match = re.search(r"next-hop (\S+)", entry)
        next_hop = next_hop_match.group(1) if next_hop_match else ""

        as_path_match = re.search(r"as-path \[ (.+?) \]", entry)
        as_path = [int(i) for i in as_path_match.group(1).split()] if as_path_match else []

        community_match = re.search(r"community \[ (.+?) \]", entry)
        community = community_match.group(1).split() if community_match else []

        med_match = re.search(r"med (\d+)", entry)
        med = int(med_match.group(1)) if med_match else 0

        rib_in[neighbor][route] = {
            "next-hop": next_hop,
            "as-path": as_path,
            "community": community,
            "med": med,
        }
    return rib_in