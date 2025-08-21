#!/usr/bin/env python3

"""Manages the ExaBGP test peer for the live autograder."""

import os
import time

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
    # Ensure config files exist
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
    time.sleep(5) # Give it a moment to start up
    print(f"ExaBGP container {EXABGP_CTN_NAME} started.")

def configure_exabgp_for_as(asn):
    """Generates an exabgp.conf to peer with the specified student AS."""
    # This function would need to be implemented based on how you want to connect
    # to the student's live AS. A possible approach is to create veth pairs
    # to link the ExaBGP container to each of the student's border routers.
    # For now, this is a placeholder.
    print(f"(Placeholder) Configuring ExaBGP to peer with AS {asn}.")
    # In a real implementation, you would:
    # 1. Get border routers for the ASN.
    # 2. Create veth pairs between EXABGP_CTN_NAME and each border router container.
    # 3. Assign IP addresses to both ends of the veth pairs.
    # 4. Write the corresponding `neighbor` blocks to exabgp.conf.
    # 5. Reload ExaBGP.
    pass

def clear_exabgp_config():
    """Clears the ExaBGP configuration."""
    exec_ctn(EXABGP_CTN_NAME, ["exabgpcli shutdown"], shell="bash")
    with open(EXABGP_CONF_LOCAL_PATH, "w") as f:
        f.write("")
    exec_ctn(EXABGP_CTN_NAME, [f"exabgp -e {EXABGP_ENV_CTN_PATH} {EXABGP_CONF_CTN_PATH} &"], shell="bash")
    print("Cleared ExaBGP configuration.")

# Functions from the old exabgp_utils.py can be adapted and placed here
def announce_exabgp_route(neighbor, prefix, next_hop, **kwargs):
    """Announces a route from the ExaBGP test peer."""
    ann = f"neighbor {neighbor} announce route {prefix} next-hop {next_hop}"
    if kwargs.get('as_path'):
        ann += f" as-path [ {' '.join(map(str, kwargs['as_path']))} ]"
    if kwargs.get('community'):
        ann += f" community [ {' '.join(kwargs['community'])} ]"
    # Add other BGP attributes as needed
    cmd = [f"exabgpcli {ann}"]
    exec_ctn(EXABGP_CTN_NAME, cmd, shell="bash")

def withdraw_exabgp_route(neighbor, prefix):
    """Withdraws a route from the ExaBGP test peer."""
    ann = f"neighbor {neighbor} withdraw route {prefix}"
    cmd = [f"exabgpcli {ann}"]
    exec_ctn(EXABGP_CTN_NAME, cmd, shell="bash")

def get_exabgp_rib_in():
    """Parses the adj-rib-in from the ExaBGP test peer."""
    # This function would be similar to the original one in exabgp_utils.py
    # but would run inside the single EXABGP_CTN_NAME container.
    pass
