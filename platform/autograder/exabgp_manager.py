#!/usr/bin/env python3

"""Manages the ExaBGP test peer for the live autograder."""

import os
import time
import re
from collections import defaultdict

from ctn_utils import client, exec_ctn, get_ctn_name_lst, remove_ctn
import live_mnet_utils as mnet

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
    # This is a complex function that requires creating veth pairs and IPs.
    # It will be left as a placeholder as it requires sudo and direct host modification.
    print(f"(Placeholder) Configuring ExaBGP to peer with AS {asn}.")
    pass

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