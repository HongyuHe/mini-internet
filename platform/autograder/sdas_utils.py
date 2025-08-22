#!/usr/bin/env python3

"""Inner functions to create shadow as."""

import argparse
import os
import time
import shutil
import subprocess

from ctn_utils import (
    client,
    copy_ctn_file,
    copy_local_file,
    exec_ctn,
    get_ctn_name_lst,
    remove_ctn,
)
from mnet_utils import (
    NB_CONN,
    REGION_NAMES,
    ROUTER_LINK_TO_ID,
    SD_CTN_PREFIX,
    IXP_ASNS,
    get_nb_asn_r,
    get_r_ctn_name,
    get_exp_intf_ip,
    get_ext_intf_names,
    ROUTINATOR_R,
    get_act_h_intf_subnet,
    get_h_gw,
    get_valid_ext_link_intfs,
    L2_SW_NAMES,
    get_h_ctn_name,
    get_s_ctn_name,
    L2_HOST_NAMES,
    L2_REGION_TO_SW,
    L2_SW_CONN,
    L2_L3_CONN,
    VLAN_TAGS,
    ExtIntfs,
    add_h_gw,
    add_h_intf,
    get_exp_h_intf_name,
    TUNNEL_REGIONS,
    add_r_tunnel,
)
from parse_kernel_config import get_default_via, get_host_subnet, get_router_tunnel

# set up containers used in shadow AS

PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
CUR_DIR = os.getcwd()
CONFIG_DIR = os.path.join(CUR_DIR, "configs")
DEAMON_PATH = os.path.join(CONFIG_DIR, "daemons")
CONF_LOCAL_PATH = os.path.join(os.getcwd(), "gitlab_configs_copy")
FRR_CTN_PATH = "/etc/frr/frr.conf"
CONNECT_SD_FILE = "connect_shadow_as.sh"
FRR_RELOAD_PATH = "/usr/lib/frr/frr-reload.py"
# FULL_CONF_FILE = "init_full_conf.sh"
EXABGP_CONF_CTN_PATH = "/etc/exabgp/exabgp.conf"
EXABGP_LOG_CTN_PATH = "/etc/exabgp/exabgp.log"
EXABGP_ENV_CTN_PATH = "/etc/exabgp/exabgp.env"
EXABGP_ENV_PATH = os.path.join(CONFIG_DIR, "exabgp.env")
CUR_ASN_PATH = os.path.join(CUR_DIR, "cur_asn.txt")
EXABGP_CONF_LOCAL_PATH = os.path.join(CUR_DIR, "exabgp.conf")
EXABGP_LOG_LOCAL_PATH = os.path.join(CUR_DIR, "exabgp.log")
# RPKI_LOCAL_DIR = os.path.join(PARENT_DIR, "groups/rpki")
CRT_LOCAL_PATH = os.path.join(CONFIG_DIR, "root.crt")
CRT_CTN_PATH = "/usr/local/share/ca-certificates/root.crt"
TAL_LOCAL_PATH = os.path.join(CONFIG_DIR, "tals")
TAL_CTN_PATH = "/root/.rpki-cache/tals"
RPKI_EXCEPT_CTN_PATH = "/root/rpki_exceptions.json"
# REPO_CTN_DIR = "/root/.rpki-cache/"
RPKI_EXCEPT_LOCAL_PATH = os.path.join(CONFIG_DIR, "rpki_exceptions.json")
SW_DB_CTN_PATH = "/home/switch.db"
REPO_CTN_PATH = "/root/.rpki-cache/repository"
ROUTINATOR_WAIT = 40
SW_DB_WAIT = 3
EXABGP_WAIT = 10


def get_shadow_ctn_name(name, ctn_type=""):
    """Return the shadow router container name."""
    if ctn_type == "router":
        return get_r_ctn_name(SD_CTN_PREFIX, name)
    elif ctn_type == "host":
        return get_h_ctn_name(SD_CTN_PREFIX, name)
    elif ctn_type == "switch":
        return get_s_ctn_name(SD_CTN_PREFIX, name)
    else:
        return f"{SD_CTN_PREFIX}_{name}"

        # def create_local_config_dir():
        #     """Create local config dir to be mounted later."""
        #     print("\nCreating local config directory...")
        #     # create sub dir for each as router
        #     for r_name in REGION_NAMES:
        #         # l3 router
        #         r_path = os.path.join(CONF_LOCAL_PATH, f"{r_name}router")
        #         if not os.path.exists(r_path):
        #             os.makedirs(r_path)
        #             subprocess.call(["touch", os.path.join(r_path, "frr.conf")])
        #             # print(f"  Created config directory and frr.conf for {r_name}router.")
        #         # l3 host
        #         h_path = os.path.join(CONF_LOCAL_PATH, f"{r_name}host")
        #         if not os.path.exists(h_path):
        #             os.makedirs(h_path)
        #             # print(f"  Created config directory for {r_name}host.")

        #     # l2 switch
        #     for sw_name in L2_SW_NAMES:
        #         s_path = os.path.join(CONF_LOCAL_PATH, sw_name)
        #         if not os.path.exists(s_path):
        #             os.makedirs(s_path)
        #             # print(f"  Created config directory for {sw_name}.")

        #     # l2 host
        #     for h_name in L2_HOST_NAMES:
        #         h_path = os.path.join(CONF_LOCAL_PATH, h_name)
        #         if not os.path.exists(h_path):
        #             os.makedirs(h_path)
        #             # print(f"  Created config directory for {h_name}.")

        # r_name = "EXABGP"
        # r_path = os.path.join(CONF_LOCAL_PATH, r_name)
        # if not os.path.exists(r_path):
        #     os.makedirs(r_path)
        #     subprocess.call(["touch", os.path.join(r_path, "exabgp.conf")])
        #     subprocess.call(["touch", os.path.join(r_path, "exabgp.log")])
        # print("  Created ExaBGP directory and config.")


log_config = {"type": "json-file", "config": {"max-size": "1m", "max-file": "3"}}


def create_as_ctns(asn):
    """Start all containers within a shadow as."""
    print("\nCreating router containers in shadow AS...")
    for r_name in REGION_NAMES:
        sd_ctn_name = get_shadow_ctn_name(r_name, "router")
        frr_local_path = os.path.join(
            CONF_LOCAL_PATH, f"group{asn}/{r_name}/router.conf"
        )
        client.containers.run(
            image="miniinterneteth/d_router",
            name=sd_ctn_name,
            nano_cpus=2000000000,
            network_mode="none",
            cap_add=["ALL"],
            cap_drop=["SYS_RESOURCE"],
            hostname=f"{r_name}_router",
            pids_limit=100,
            detach=True,
            volumes={
                DEAMON_PATH: {"bind": "/etc/frr/daemons", "mode": "rw"},
                "/etc/timezone": {"bind": "/etc/timezone", "mode": "ro"},
                frr_local_path: {"bind": FRR_CTN_PATH, "mode": "rw"},
            },
            sysctls={
                "net.ipv4.ip_forward": "1",
                "net.ipv4.icmp_ratelimit": "0",
                "net.ipv4.fib_multipath_hash_policy": "1",
                "net.ipv4.conf.all.rp_filter": "0",
                "net.ipv4.conf.default.rp_filter": "0",
                "net.ipv4.conf.lo.rp_filter": "0",
                "net.ipv4.icmp_echo_ignore_broadcasts": "0",
                "net.ipv4.tcp_l3mdev_accept": "1",
                "net.ipv6.conf.all.disable_ipv6": "0",
                "net.ipv6.conf.all.forwarding": "1",
                "net.ipv6.icmp.ratelimit": "0",
                "net.mpls.conf.lo.input": "1",
                "net.mpls.platform_labels": "1048575",
            },
            environment=["VPN_OBSERVER_SLEEP=500"],
            log_config=log_config,
        )
        # wait more time to let config to be loaded
        time.sleep(4)
        # print(f"  Created router container {sd_ctn_name}.")

    print("\nCreating L2 switch containers in shadow AS...")
    for sw_name in L2_SW_NAMES:
        sd_ctn_name = get_shadow_ctn_name(sw_name, "switch")
        switch_db_local_path = os.path.join(
            CONF_LOCAL_PATH, f"group{asn}/{sw_name}/switch.db"
        )
        client.containers.run(
            image="miniinterneteth/d_switch",
            name=sd_ctn_name,
            nano_cpus=2000000000,
            network_mode="none",
            cap_add=["ALL", "NET_ADMIN"],
            cap_drop=["SYS_RESOURCE"],
            hostname=sw_name,
            pids_limit=1024,
            detach=True,
            volumes={
                "/etc/timezone": {"bind": "/etc/timezone", "mode": "ro"},
                "/etc/localtime": {"bind": "/etc/localtime", "mode": "ro"},
                switch_db_local_path: {"bind": SW_DB_CTN_PATH, "mode": "rw"},
            },
            sysctls={
                "net.ipv4.ip_forward": "1",
                "net.ipv4.icmp_ratelimit": "0",
                "net.ipv4.fib_multipath_hash_policy": "1",
                "net.ipv4.conf.all.rp_filter": "0",
                "net.ipv4.conf.default.rp_filter": "0",
                "net.ipv4.conf.lo.rp_filter": "0",
                "net.ipv4.icmp_echo_ignore_broadcasts": "0",
                "net.ipv6.conf.all.disable_ipv6": "0",
                "net.ipv6.conf.all.forwarding": "1",
                "net.ipv6.icmp.ratelimit": "0",
            },
            log_config=log_config,
        )

        # wait for ovs database to setup
        time.sleep(SW_DB_WAIT)
        # create bridges
        sw_id = int(sw_name[-1])
        sys_id = ":".join([f"{sw_id}{sw_id}"] * 6)
        cmd = [
            f"ovs-vsctl -- add-br br0 -- set bridge br0 stp_enable=true -- set-fail-mode br0 standalone -- set bridge br0 other_config:stp-system-id={sys_id} -- set bridge br0 other_config:stp-priority={sw_id}"
        ]
        exec_ctn(sd_ctn_name, cmd, shell="bash")

        # print(f"  Created switch container {sd_ctn_name}.")

    print("\nCreating host containers in shadow AS...")
    for host in L2_HOST_NAMES + REGION_NAMES:
        if host == ROUTINATOR_R:
            continue
        sd_ctn_name = get_shadow_ctn_name(host, "host")
        client.containers.run(
            image="miniinterneteth/d_host",
            name=sd_ctn_name,
            nano_cpus=2000000000,
            network_mode="none",
            cap_add=["NET_ADMIN"],
            cap_drop=["SYS_RESOURCE"],
            hostname=host,
            pids_limit=100,
            detach=True,
            volumes={
                "/etc/timezone": {"bind": "/etc/timezone", "mode": "ro"},
                "/etc/localtime": {"bind": "/etc/localtime", "mode": "ro"},
            },
            sysctls={
                "net.ipv4.icmp_ratelimit": "0",
                "net.ipv4.icmp_echo_ignore_broadcasts": "0",
                "net.ipv6.conf.all.disable_ipv6": "0",
                "net.ipv6.icmp.ratelimit": "0",
            },
            log_config=log_config,
        )
        # print(f"  Created host container {sd_ctn_name}.")

    # start routinator
    sd_ctn_name = get_shadow_ctn_name(ROUTINATOR_R, "host")
    rpki_cache_path = os.path.join(CONF_LOCAL_PATH, f"group{asn}/{ROUTINATOR_R}")
    subprocess.run(f'sudo tar -xzf "{rpki_cache_path}/host.rpki_cache" -C "{rpki_cache_path}"', shell=True)
    print("extracted")
    repo_local_path = os.path.join(
        CONF_LOCAL_PATH, f"group{asn}/{ROUTINATOR_R}/repository"
    )
    client.containers.run(
        image="d_routinator",
        name=sd_ctn_name,
        nano_cpus=2000000000,
        network_mode="none",
        cap_add=["NET_ADMIN"],
        hostname=f"{ROUTINATOR_R}_host",
        pids_limit=100,
        detach=True,
        volumes={
            "/etc/timezone": {"bind": "/etc/timezone", "mode": "ro"},
            "/etc/localtime": {"bind": "/etc/localtime", "mode": "ro"},
            CRT_LOCAL_PATH: {"bind": CRT_CTN_PATH, "mode": "ro"},
            TAL_LOCAL_PATH: {"bind": TAL_CTN_PATH, "mode": "ro"},
            RPKI_EXCEPT_LOCAL_PATH: {"bind": RPKI_EXCEPT_CTN_PATH, "mode": "ro"},
            repo_local_path: {"bind": REPO_CTN_PATH, "mode": "rw"},
        },
        sysctls={
            "net.ipv4.icmp_ratelimit": "0",
            "net.ipv4.icmp_echo_ignore_broadcasts": "0",
            "net.ipv6.conf.all.disable_ipv6": "0",
            "net.ipv6.icmp.ratelimit": "0",
        },
        log_config=log_config,
    )
    # print(f"  Created routinator container {sd_ctn_name}.")


def create_as_int_links(asn):
    """Create internal links in shadow as."""
    print("\nCreating internal links in shadow AS...")
    # between routers
    for r_a, r_b in ROUTER_LINK_TO_ID:
        ctn_a = get_shadow_ctn_name(r_a, "router")
        intf_a = f"port_{r_b}"
        ctn_b = get_shadow_ctn_name(r_b, "router")
        intf_b = f"port_{r_a}"
        cmd = [
            os.path.join(os.getcwd(), CONNECT_SD_FILE),
            "add_link",
            ctn_a,
            intf_a,
            ctn_b,
            intf_b,
        ]
        subprocess.call(["sudo", "bash"] + cmd)
        # print(f"  Link {intf_a}--{intf_b} is created between {r_a} and {r_b}.")

    # between l3 routers and hosts
    for r_name in REGION_NAMES:
        ctn_r = get_shadow_ctn_name(r_name, "router")
        ctn_h = get_shadow_ctn_name(r_name, "host")

        cmd = [
            os.path.join(os.getcwd(), CONNECT_SD_FILE),
            "add_link",
            ctn_h,
            f"{r_name}router",
            ctn_r,
            "host",
        ]
        subprocess.call(["sudo", "bash"] + cmd)
        # print(f"  Link between {r_name}host and {r_name}router is created.")

    # between l2 switches and hosts
    for l2_h in L2_HOST_NAMES:
        ctn_h = get_shadow_ctn_name(l2_h, "host")
        sw_id = L2_REGION_TO_SW[l2_h.split("_")[1]]
        ctn_s = get_shadow_ctn_name(f"S{sw_id}", "switch")
        intf_h = f"{asn}-S{sw_id}"
        intf_s = f"{asn}-{l2_h}"
        cmd = [
            os.path.join(os.getcwd(), CONNECT_SD_FILE),
            "add_link",
            ctn_h,
            intf_h,
            ctn_s,
            intf_s,
        ]
        subprocess.call(["sudo", "bash"] + cmd)
        # add ports
        cmd = [f"ovs-vsctl add-port br0 {intf_s}"]
        exec_ctn(ctn_s, cmd, shell="bash")
        # print(f"  Link between {l2_h} and S{sw_id} is created.")

    # between l2 switches
    for sw_a, sw_b in L2_SW_CONN:
        ctn_sw_a = get_shadow_ctn_name(sw_a, "switch")
        ctn_sw_b = get_shadow_ctn_name(sw_b, "switch")
        intf_a = f"{asn}-{sw_b}"
        intf_b = f"{asn}-{sw_a}"
        cmd = [
            os.path.join(os.getcwd(), CONNECT_SD_FILE),
            "add_link",
            ctn_sw_a,
            intf_a,
            ctn_sw_b,
            intf_b,
        ]
        subprocess.call(["sudo", "bash"] + cmd)
        # add port on sw
        cmd = [f"ovs-vsctl add-port br0 {intf_a} -- set Port {intf_a} trunks=0"]
        exec_ctn(ctn_sw_a, cmd, shell="bash")
        cmd = [f"ovs-vsctl add-port br0 {intf_b} -- set Port {intf_b} trunks=0"]
        exec_ctn(ctn_sw_b, cmd, shell="bash")

        # print(f"  Link between {sw_a} and {sw_b} is created.")

    # between l2 switch and l3 gateway router
    for sw, gw_r in L2_L3_CONN:
        ctn_sw = get_shadow_ctn_name(sw, "switch")
        ctn_r = get_shadow_ctn_name(gw_r, "router")
        intf_s = f"{gw_r}router"
        intf_r = f"{gw_r}-L2"
        cmd = [
            os.path.join(os.getcwd(), CONNECT_SD_FILE),
            "add_link",
            ctn_sw,
            intf_s,
            ctn_r,
            intf_r,
        ]
        subprocess.call(["sudo", "bash"] + cmd)
        # add switch ports
        cmd = [f"ovs-vsctl add-port br0 {intf_s}"]
        exec_ctn(ctn_sw, cmd, shell="bash")
        # add vlan links on router
        for vlan in VLAN_TAGS:
            cmd = [
                os.path.join(os.getcwd(), CONNECT_SD_FILE),
                "add_vlan",
                ctn_r,
                gw_r,
                str(vlan),
            ]
            subprocess.call(["sudo", "bash"] + cmd)
        # print(f"  Links between {sw} and {gw_r}router is created.")


def record_cur_asn(asn):
    """Record current asn in a file."""
    with open(CUR_ASN_PATH, "w") as f:
        f.write(f"{asn}")


def get_cur_asn():
    """Return the current ASN running on shadow AS."""
    with open(CUR_ASN_PATH, "r") as f:
        return int(f.read())


# def clear_as_int_links():
#     """Clear internal links in shadow as."""
#     print("\nClearing internal links for shadow AS...")
#     for r_a, r_b in ROUTER_LINK_TO_ID:
#         ctn_a = get_shadow_ctn_name(r_a, "router")
#         intf_a = f"port_{r_b}"
#         ctn_b = get_shadow_ctn_name(r_b, "router")
#         intf_b = f"port_{r_a}"
#         cmd = [os.path.join(os.getcwd(), CONNECT_SD_FILE), "delete_link", ctn_a, intf_a]
#         subprocess.call(["sudo", "bash"] + cmd)
#         cmd = [os.path.join(os.getcwd(), CONNECT_SD_FILE), "delete_link", ctn_b, intf_b]
#         subprocess.call(["sudo", "bash"] + cmd)
#         # print(f"  Link {intf_a}--{intf_b} is created between {r_a} and {r_b}.")

#     # clear link for routinator
#     cmd = [
#         os.path.join(os.getcwd(), CONNECT_SD_FILE),
#         "delete_link",
#         get_shadow_ctn_name(ROUTINATOR_R, "host"),
#         f"{ROUTINATOR_R}router",
#     ]
#     subprocess.call(["sudo", "bash"] + cmd)
#     cmd = [
#         os.path.join(os.getcwd(), CONNECT_SD_FILE),
#         "delete_link",
#         get_shadow_ctn_name(ROUTINATOR_R, "router"),
#         "host",
#     ]
#     subprocess.call(["sudo", "bash"] + cmd)


# def clear_as_ext_links():
#     """Clear external interface for current shadow as."""
#     print("\nClearing legacy external link for shadow AS...")
#     asn = get_cur_asn()
#     for nb_name, r_name in NB_CONN.items():
#         ctn_r = get_shadow_ctn_name(r_name, "router")
#         ctn_exabgp = get_shadow_ctn_name("EXABGP")
#         intf_r, intf_nb = get_ext_intf_names(asn, nb_name)

#         cmd = [os.path.join(os.getcwd(), CONNECT_SD_FILE), "delete_link", ctn_r, intf_r]
#         subprocess.call(["sudo", "bash"] + cmd)
#         cmd = [
#             os.path.join(os.getcwd(), CONNECT_SD_FILE),
#             "delete_link",
#             ctn_exabgp,
#             intf_nb,
#         ]
#         subprocess.call(["sudo", "bash"] + cmd)
#         # print(f"  External link with {intf_nb} is deleted.")


# def clear_legacy_intf(prev_asn):
#     """Clear legacy interface on shadow AS."""
#     # NOTE: for some reason this function cannot be
#     # integrated to clear_as_ext_link(), maybe because
#     # I need to first update config
#     print("\nClearing legacy shadow AS interface...")
#     for nb_name, r_name in NB_CONN.items():
#         intf_r, _ = get_ext_intf_names(prev_asn, nb_name)
#         cmd = ["config", f"no interface {intf_r}"]
#         ctn_r = get_shadow_ctn_name(r_name, "router")
#         exec_ctn(ctn_r, cmd, shell="vtysh")

#     # clear legacy routinator interface
#     act_h_subnet = get_act_h_intf_subnet(
#         prev_asn, ROUTINATOR_R, f"{ROUTINATOR_R}router"
#     )
#     cmd = [f"ip addr del {act_h_subnet} dev {ROUTINATOR_R}router"]
#     exec_ctn(get_shadow_ctn_name(ROUTINATOR_R, "host"), cmd, shell="bash")
#     act_h_gw = get_h_gw(prev_asn, ROUTINATOR_R, v6=False)
#     cmd = [f"ip route del default via {act_h_gw}"]
#     exec_ctn(get_shadow_ctn_name(ROUTINATOR_R, "host"), cmd, shell="bash")


def clear_shadow_as():
    """Clear shadow as by removing ctn and binded config dir."""
    print("\nClearing legacy shadow AS...")
    # print("  Removing legacy containers...")
    shadow_ctn_lst = get_ctn_name_lst(f"^{SD_CTN_PREFIX}_*")
    for ctn_name in shadow_ctn_lst:
        remove_ctn(ctn_name)
    with open(EXABGP_CONF_LOCAL_PATH, "w") as _:
        pass
    with open(EXABGP_LOG_LOCAL_PATH, "w") as _:
        pass
    # print(f"  Removing legacy directory in {CONF_LOCAL_PATH}...")
    # for item in os.listdir(CONF_LOCAL_PATH):
    #     item_path = os.path.join(CONF_LOCAL_PATH, item)
    #     if os.path.isdir(item_path):
    #         shutil.rmtree(item_path)
    # print(f"  Removed directory {item_path}.")
    # clear_as_int_links()
    # clear_as_ext_links()


def shadow_as_exists():
    """Check if there exists a shadow AS."""
    if not get_ctn_name_lst(f"^{SD_CTN_PREFIX}_*"):
        return False
    return True


def start_exabgp_ctn(asn):
    """Start exabgp on each neighbor."""
    print("\nStarting ExaBGP container for shadow AS...")
    # print(f"  Waiting {EXABGP_WAIT}sec for shadow AS to load configuration...")
    # time.sleep(EXABGP_WAIT)
    r_name = "EXABGP"
    sd_ctn_name = get_shadow_ctn_name("EXABGP")
    client.containers.run(
        image="yuchen14/d_exabgp",
        name=sd_ctn_name,
        network_mode="none",
        privileged=True,
        pids_limit=100,
        hostname=r_name,
        volumes={
            EXABGP_CONF_LOCAL_PATH: {"bind": EXABGP_CONF_CTN_PATH, "mode": "rw"},
            EXABGP_LOG_LOCAL_PATH: {"bind": EXABGP_LOG_CTN_PATH, "mode": "rw"},
        },
        log_config=log_config,
        detach=True,
    )
    # print("  ExaBGP container is created.")

    # add external links and neighbor conf for exabgp
    for nb_name, r_name in NB_CONN.items():
        intf_r, intf_nb = get_ext_intf_names(asn, nb_name)
        ctn_exabgp = get_shadow_ctn_name("EXABGP")
        ctn_r = get_shadow_ctn_name(r_name, "router")
        # create peering session
        cmd = [
            os.path.join(os.getcwd(), CONNECT_SD_FILE),
            "add_link",
            ctn_exabgp,
            intf_nb,
            ctn_r,
            intf_r,
        ]
        subprocess.call(["sudo", "bash"] + cmd)

    print(f"  Waiting {EXABGP_WAIT} sec to set up extrenal links...")
    time.sleep(EXABGP_WAIT)

    for nb_name, r_name in NB_CONN.items():
        nb_asn, nb_r = get_nb_asn_r(asn, nb_name)
        ext_link_intfs = get_valid_ext_link_intfs(asn)
        # add config
        # r_ext_ip = get_exp_intf_ip("ext", asn, r_name, nb_r)
        # nb_ext_ip = get_exp_intf_ip("ext", nb_asn, nb_r, r_name)
        intf_r, intf_nb = get_ext_intf_names(asn, nb_name)
        if nb_name not in ext_link_intfs:
            print(
                f"  Peering session between {r_name} and {nb_r}({nb_asn})"
                + " is invalid, not created."
            )
        else:
            r_ip = ExtIntfs(*ext_link_intfs[nb_name]).r_ip
            nb_ip = ExtIntfs(*ext_link_intfs[nb_name]).nb_ip

            nb_lo = get_exp_intf_ip("lo", nb_asn, nb_r)
            cmd = [
                os.path.join(os.getcwd(), CONNECT_SD_FILE),
                "add_addr",
                ctn_exabgp,
                nb_ip,
                intf_nb,
            ]
            subprocess.call(["sudo", "bash"] + cmd)

            with open(EXABGP_CONF_LOCAL_PATH, "a") as f:
                f.write(f"neighbor {r_ip} " + "{\n")
                f.write(f"    description '{nb_name}--{r_name}';\n")
                f.write(f"    router-id {nb_lo};\n")
                f.write(f"    local-address {nb_ip};\n")
                f.write(f"    local-as {nb_asn};\n")
                f.write(f"    peer-as {asn};\n")
                f.write("    family {\n")
                f.write("         ipv4 unicast;\n")
                f.write("    }\n")
                # advertise neighbor own routes
                if nb_asn not in IXP_ASNS:
                    f.write("    static {\n")
                    f.write(f"         route {nb_asn}.0.0.0/8 next-hop self;\n")
                    f.write("    }\n")
                f.write("}\n")
            print(
                f"  Peering session between {r_name} and {nb_r}({nb_asn})"
                + " is created on ExaBGP."
            )

    # start exabgp
    cmd = [
        f"exabgp -e {EXABGP_ENV_CTN_PATH} {EXABGP_CONF_CTN_PATH} "
        + f"> {EXABGP_LOG_CTN_PATH} &"
    ]
    exec_ctn(get_shadow_ctn_name("EXABGP"), cmd, shell="bash")
    print("  ExaBGP service is started.")


def start_shadow_as(asn):
    """Start the shadow AS by either creating or updating one."""
    create_shadow_as(asn)
    # if not shadow_as_exists():
    #     create_shadow_as(asn)
    # else:
    #     update_shadow_as(asn)


def create_shadow_as(asn):
    """
    Create shawdow AS from scratch.

    Given the asn, create the shadow as and its neighborinig router containers.
    AS configs are also loaded at this stage.
    """
    print(f"\nCreating shadow AS for AS {asn}...")
    # clear_shadow_as()
    # create_local_config_dir()
    # create_nb_ctns()
    # create_as_ext_links(asn)
    
    # create_as_ctns(asn)
    # create_as_int_links(asn)
    # load_as_config(asn)
    # print(f"\nShadow AS for AS {asn} is created.")
    
    start_exabgp_ctn(asn)
    record_cur_asn(asn)


# def update_shadow_as(asn):
#     """
#     Update shadow as with the new testing AS.

#     Internal containers are not removed, but external routers and links
#     are flushed for re-configuration.
#     """
#     # TODO remove legacy interface on internal router
#     print(f"\nUpdating shadow AS for AS {asn}...")
#     prev_asn = get_cur_asn()
#     clear_as_ext_links()
#     # remove nb containers only
#     print("\nRemoving ExaBGP container and config...")
#     remove_ctn(get_shadow_ctn_name("EXABGP"))
#     exabgp_conf_path = os.path.join(CONF_LOCAL_PATH, "EXABGP/exabgp.conf")
#     with open(exabgp_conf_path, "w") as _:
#         pass
#     # create_nb_ctns()
#     # create_as_ext_links(asn)
#     clear_legacy_intf(prev_asn)
#     load_as_config(asn, prev_asn)
#     start_exabgp_ctn(asn)
#     record_cur_asn(asn)
#     print(f"\nShadow AS for AS {asn} is updated.")


def load_as_config(asn, prev_asn=""):
    """Load the router config of the as and its nb routers to shadow as.

    This function should be load only after shadow as has been set up.
    """
    print(f"\nLoading AS {asn}'s config into shadow AS...")
    # for r_name in REGION_NAMES:
    #     frr_local_path = os.path.join(CONF_LOCAL_PATH, f"g{asn}/{r_name}/router.conf")
    #     ctn_name = get_r_ctn_name(asn, r_name)
    #     # TODO copy from saved config instead of frr.conf
    #     sd_ctn_name = get_shadow_ctn_name(r_name, "router")
    #     copy_local_file(sd_ctn_name, frr_local_path, FRR_CTN_PATH)
    #     cmd = [f"python3 {FRR_RELOAD_PATH} --reload {FRR_CTN_PATH}"]
    #     exec_ctn(sd_ctn_name, cmd, shell="bash")
    # print(f"  Loaded {r_name} config.")

    # load routinator repo
    # as_ctn_name = f"{asn}_{ROUTINATOR_R}host"
    # sd_ctn_name = get_shadow_ctn_name(ROUTINATOR_R, "host")
    # copy_ctn_file(
    #     as_ctn_name,
    #     os.path.join(REPO_CTN_DIR, "repository"),
    #     os.path.join(CONF_LOCAL_PATH, f"{ROUTINATOR_R}host"),
    # )
    # copy_local_file(
    #     sd_ctn_name,
    #     os.path.join(CONF_LOCAL_PATH, f"{ROUTINATOR_R}host/repository"),
    #     REPO_CTN_DIR,
    # )

    # # remove legacy interface
    # if prev_asn:
    #     prev_h_subnet = get_act_h_intf_subnet(
    #         prev_asn, ROUTINATOR_R, f"{ROUTINATOR_R}router"
    #     )
    #     cmd = [f"ip addr del {prev_h_subnet} dev {ROUTINATOR_R}router"]
    #     exec_ctn(get_shadow_ctn_name(ROUTINATOR_R, "host"), cmd, shell="bash")

    # load routinator host interface
    # load all hosts interface and gateways
    for h_name in L2_HOST_NAMES + REGION_NAMES:
        intf_name = get_exp_h_intf_name(asn, h_name)
        act_ip_4 = get_host_subnet(asn, h_name, intf_name, v6=False)
        add_h_intf(SD_CTN_PREFIX, h_name, act_ip_4, intf_name, v6=False)
        act_gw_4 = get_default_via(asn, h_name, v6=False)
        add_h_gw(SD_CTN_PREFIX, h_name, act_gw_4, v6=False)

        if h_name in L2_HOST_NAMES:
            act_ip_6 = get_host_subnet(asn, h_name, intf_name, v6=True)
            add_h_intf(SD_CTN_PREFIX, h_name, act_ip_6, intf_name, v6=True)
            act_gw_6 = get_default_via(asn, h_name, v6=True)
            add_h_gw(SD_CTN_PREFIX, h_name, act_gw_6, v6=True)

        # print(f"  Loaded host {h_name} config.")
    # add router tunnel
    for r_name in TUNNEL_REGIONS:
        tunnel_config = get_router_tunnel(asn, r_name)
        for t_name, t_config in tunnel_config.items():
            add_r_tunnel(
                SD_CTN_PREFIX,
                r_name,
                t_name,
                t_config["remote"],
                t_config["local"],
                t_config["ttl"],
                t_config["subnet"],
            )

    for s_name in L2_SW_NAMES:
        # restore switch db
        sd_ctn_name = get_shadow_ctn_name(s_name, "switch")
        cmd = [f"ovsdb-client restore < {SW_DB_CTN_PATH}"]
        exec_ctn(sd_ctn_name, cmd, shell="bash")
        # print(f"  Loaded switch {h_name} config.")

    # TODO: load tunnel config
    # act_h_subnet = get_act_h_intf_subnet(asn, ROUTINATOR_R, f"{ROUTINATOR_R}router")
    # cmd = [f"ip addr add {act_h_subnet} dev {ROUTINATOR_R}router"]
    # exec_ctn(get_shadow_ctn_name(ROUTINATOR_R, "host"), cmd, shell="bash")
    # act_h_gw = get_h_gw(asn, ROUTINATOR_R, v6=False)
    # cmd = [f"ip route add default via {act_h_gw}"]
    # exec_ctn(get_shadow_ctn_name(ROUTINATOR_R, "host"), cmd, shell="bash")
    # print("  Loaded Routinator config.")

    print(f"\nWaiting {ROUTINATOR_WAIT} sec for BGP convergence...")
    # TODO: is it because slow routinator response?
    time.sleep(ROUTINATOR_WAIT)
    # reset rpki and RIB
    for r_name in REGION_NAMES:
        ctn_name = get_shadow_ctn_name(r_name, "router")
        cmd = ["/usr/var/frr/frrinit.sh", "force-reload"]
        exec_ctn(ctn_name, cmd, shell="bash")
        ctn_name = get_shadow_ctn_name(r_name, "router")
        cmd = ["config", "rpki", "rpki reset"]
        exec_ctn(ctn_name, cmd, shell="vtysh")
        cmd = ["clear ip bgp *"]
        # NOTE: router can re-converge when grading part 1
        exec_ctn(ctn_name, cmd, shell="vtysh")
        print(f"  Reset {r_name} RPKI config.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--asn", type=int, help="student ASN", required=False)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", action="store_true", help="start the shadow AS")
    group.add_argument("--clear", action="store_true", help="clear existing shadow AS")
    args = parser.parse_args()

    if args.start:
        start_shadow_as(args.asn)
    elif args.clear:
        clear_shadow_as()
