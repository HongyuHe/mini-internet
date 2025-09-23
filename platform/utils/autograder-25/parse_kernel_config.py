import os
import json

FILE_DIR = os.path.join(os.getcwd(), "gitlab_configs/")


def cached_function(func):
    cache = {}

    def wrapper(*args, **kwargs):
        key = args + tuple(sorted(kwargs.items()))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    return wrapper


def get_hostip_content(as_number, host_name, if_name):
    # read the file and print the contents
    # assert (
    #     int(if_name.split("-")[0]) == as_number
    # ), "interface name {} doesn't match AS number {}".format(if_name, as_number)
    filename = FILE_DIR + "group{}/{}/host.ip".format(as_number, host_name)
    # try to read the file
    try:
        f = open(filename, "r")
    except:
        print("Warning: file {} doesn't exist".format(filename))
        return []
    f = open(filename, "r")
    # add a assert
    # use readlines to read all lines in the file
    # The variable "content" is a list containing all lines in the file
    content = f.readlines()
    f.close()
    line_start_num = 0
    line_end_num = 0
    line_found = False
    for i in range(len(content)):
        if line_found == True:
            if content[i].startswith(" ") == False:
                break
            else:
                line_end_num = i
        if content[i].find(if_name) != -1 and content[i].find("@if") != -1:
            assert line_found == False
            line_start_num = i
            line_end_num = i
            line_found = True
    if line_found == True:
        return content[line_start_num + 1 : line_end_num + 1]
    else:
        return []


def get_hostroute_content(as_number, host_name):
    # read the file and print the contents
    filename = FILE_DIR + "group{}/{}/host.route".format(as_number, host_name)
    # try to read the file
    try:
        f = open(filename, "r")
    except:
        print("Warning: file {} doesn't exist".format(filename))
        return []
    f = open(filename, "r")
    content = f.readlines()
    f.close()
    for line in content:
        if line.find("default via") != -1 and line.find("dev") != -1:
            return [line]
    return []


def get_hostroute6_content(as_number, host_name):
    # read the file and print the contents
    filename = FILE_DIR + "group{}/{}/host.route6".format(as_number, host_name)
    # try to read the file
    try:
        f = open(filename, "r")
    except:
        print("Warning: file {} doesn't exist".format(filename))
        return []
    f = open(filename, "r")
    content = f.readlines()
    f.close()
    for line in content:
        if line.find("default via") != -1 and line.find("dev") != -1:
            return [line]
    return []


def get_routertunnels_content(as_number, host_name):
    # read the file and print the contents
    filename = FILE_DIR + "group{}/{}/router.tunnels".format(as_number, host_name)
    # try to read the file
    try:
        f = open(filename, "r")
    except:
        print("Warning: file {} doesn't exist".format(filename))
        return []
    f = open(filename, "r")
    content = f.readlines()
    f.close()
    ret = []
    for line in content:
        if line.startswith("sit0:") == False:
            ret.append(line)
    return ret


def uncached_get_routerrib6json_content(as_number, host_name):
    """read json file and return the content"""
    filename = FILE_DIR + "group{}/{}/router.rib6.json".format(as_number, host_name)
    # try to read the json file
    try:
        f = open(filename, "r")
    except:
        print("Warning: file {} doesn't exist".format(filename))
        return {}
    # read the json file
    if os.stat(filename).st_size == 0:
        content = {}
    else:
        content = json.load(f)
    f.close()
    ret = {}
    # iterate the keys in the dictionary
    # the key is the prefix
    for key in content:
        if key == "fe80::/64":
            continue
        vals1 = content[key]
        for val1 in vals1:
            assert "nexthops" in val1, "nexthops not found in the json file"
            vals2 = val1["nexthops"]
            for val2 in vals2:
                assert (
                    "interfaceName" in val2
                ), "interfaceName not found in the json file"
                if val2["interfaceName"] not in ret:
                    ret[val2["interfaceName"]] = set()
                    ret[val2["interfaceName"]].add(key)
                else:
                    ret[val2["interfaceName"]].add(key)
    # print(ret)
    return ret


get_routerrib6json_content = cached_function(uncached_get_routerrib6json_content)


def get_host_ipv4(content, if_name):
    for line in content:
        # remove all the sapce in the string
        tmp = line.replace(" ", "")
        if tmp.find("inet") != -1 and tmp.find("scopeglobal" + if_name + "\n") != -1:
            assert line.find("inet ") != -1, "line bad foramt"
            assert line.find("scope global " + if_name + "\n") != -1, "line bad format"
            return line.split("inet ")[1].split(" ")[0]
    return ""


def get_host_ipv6(content):
    for line in content:
        tmp = line.replace(" ", "")
        if tmp.find("inet6") != -1 and tmp.find("scopeglobal\n") != -1:
            assert line.find("inet6 ") != -1, "line bad foramt"
            assert line.find("scope global \n") != -1, "line bad format"
            return line.split("inet6 ")[1].split(" ")[0]
    return ""


def get_default_via_ipv4(content):
    for line in content:
        tmp = line.replace(" ", "")
        if tmp.find("defaultvia") != -1 and tmp.find("dev") != -1:
            assert line.find("default via ") != -1, "line bad foramt"
            assert line.find("dev") != -1, "line bad format"
            return line.split("default via ")[1].split(" ")[0]
    return ""


def get_default_via_ipv6(content):
    for line in content:
        tmp = line.replace(" ", "")
        if tmp.find("defaultvia") != -1 and tmp.find("dev") != -1:
            assert line.find("default via ") != -1, "line bad foramt"
            assert line.find("dev") != -1, "line bad format"
            return line.split("default via ")[1].split(" ")[0]
    return ""


def get_router_tunnel_v46(content, routerrib6json_1):
    """
    content: the content of router.tunnels
    routerrib6json_1: a dict, interface_name as the key, and the value is a set of ip address
    """
    ret = {}
    for line in content:
        interface_name = line.split(":")[0]
        remote_addr = line.split("remote ")[1].split(" local")[0]
        local_addr = line.split("local ")[1].split(" ttl")[0]
        ttl_num = line.split("ttl ")[1].split(" ")[0]
        ret[interface_name] = {
            "remote": remote_addr,
            "local": local_addr,
            "ttl": ttl_num,
            "subnet": []
            if interface_name not in routerrib6json_1
            else list(routerrib6json_1[interface_name]),
        }
    return ret


def uncached_get_host_subnet(as_number, host_name, if_name, v6=False):
    if v6 == False:
        return get_host_ipv4(get_hostip_content(as_number, host_name, if_name), if_name)
    else:
        return get_host_ipv6(get_hostip_content(as_number, host_name, if_name))


def uncached_get_default_via(as_number, host_name, v6=False):
    if v6 == False:
        return get_default_via_ipv4(get_hostroute_content(as_number, host_name))
    else:
        return get_default_via_ipv6(get_hostroute6_content(as_number, host_name))


def uncached_get_router_tunnel(as_number, host_name):
    return get_router_tunnel_v46(
        get_routertunnels_content(as_number, host_name),
        get_routerrib6json_content(as_number, host_name),
    )


get_host_subnet = cached_function(uncached_get_host_subnet)
get_default_via = cached_function(uncached_get_default_via)
get_router_tunnel = cached_function(uncached_get_router_tunnel)

# str_out = get_router_tunnel(129, "PHY")
# print(str_out)
