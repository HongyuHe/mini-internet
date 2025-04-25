#!/usr/bin/env bash
set -x

{
    sudo apt update -y && sudo apt upgrade -y

    #* By default, sudo probes all interfaces for their IP addresses to enable IP-based access rules. 
    #* The mini-internet will create hundreds of virtual interfaces, and 
    #* can slow down sudo (and thus your access to the server) down to a crawl. 
    echo 'Set probe_interfaces false' | sudo tee -a /etc/sudo.conf > /dev/null

    #* Install docker
    sudo apt-get update
    sudo apt-get install ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y

    sudo apt-get install openvswitch-switch -y
    sudo apt-get install openvpn -y
    sudo apt install "linux-modules-extra-$(uname -r)" -y

    #* Install molly-guard package to guard against accidental shutdowns/reboots
    sudo apt-get install molly-guard -y

    #* Increase the number of INotify instances that can be created per real user ID with the command.
    sudo sysctl fs.inotify.max_user_instances=1024

    exit 0
}