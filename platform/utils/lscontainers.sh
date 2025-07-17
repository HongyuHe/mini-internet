#!/bin/bash

printf "%-25s %-15s %-20s %-20s %-20s\n" "NAME" "CONTAINER ID" "NETWORK" "IP ADDRESS" "PORTS"
echo "----------------------------------------------------------------------------------------------"

# Loop through all container IDs
docker ps -a -q | while read container_id; do
    name=$(docker inspect --format='{{.Name}}' "$container_id" | sed 's/\///')

    # Get ports info (published ports)
    ports=$(docker inspect --format='{{range $p, $conf := .NetworkSettings.Ports}}{{$p}} -> {{(index $conf 0).HostPort}} {{end}}' "$container_id" 2>/dev/null)
    if [[ -z "$ports" ]]; then
        ports="No Ports"
    fi

    # Use 'docker inspect' to get network info in JSON
    docker inspect "$container_id" | jq -r '
        .[0].NetworkSettings.Networks 
        | to_entries[] 
        | [.key, .value.IPAddress] 
        | @tsv' | while IFS=$'\t' read -r net ip; do
            if [[ -z "$ip" ]]; then
                ip="No IP (maybe not running or no network)"
            fi
            printf "%-25s %-15s %-20s %-20s %-20s\n" "$name" "$container_id" "$net" "$ip" "$ports"
        done
done