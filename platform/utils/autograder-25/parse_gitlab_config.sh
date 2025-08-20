#!/bin/bash

# download configs from duvel
# sudo rm -r ./saved_config
# ssh duvel "sudo ./dump_configs.sh"
# rsync -az duvel:/home/yuchen/saved_config/ ./saved_config/
# ssh duvel "sudo rm -r saved_config"

# # get required files from duvel
# rsync -az duvel:/home/alex/mini_internet_project/platform/groups/rpki/root.crt ./root.crt
# rsync -az duvel:/home/alex/mini_internet_project/platform/groups/rpki/tals ./
# rsync -az duvel:/home/alex/mini_internet_project/platform/groups/g1/rpki_exceptions.json ./rpki_exceptions.json
# rsync -az duvel:/home/alex/mini_internet_project/platform/config/aslevel_links_students.txt ./aslevel_links_students.txt

# remove the "building configuration output" lines
# set -x
dir=$(pwd)
config_folder="$dir/gitlab_configs"

regions=("CAIR" "KHAR" "ADDI" "NAIR" "CAPE" "LUAN" "KINS" "ACCR")

routinator="CAIR"

asn_lst="asn_all.txt"

IFS=' ' read -ra asn_numbers < "$asn_lst"

for number in "${asn_numbers[@]}"; do
    device_folder="${config_folder}/group${number}"

    if [ -d "$device_folder" ]; then
        for region in "${regions[@]}"; do
            region_folder="${device_folder}/${region}"
            if [ -d "$region_folder" ]; then
                # # echo "Parsing router configs in $region_folder"
                # while IFS= read -r -d '' file_path; do
                #     # Remove the first 3 lines of the file
                #     sed -i '1,4d' "$file_path"
                # done < <(find "$region_folder" -type f -name "router.conf" -print0)
                
                if [ "$region" == "$routinator" ]; then
                    # echo "Parsing routinator configs"
                    while IFS= read -r -d '' file_path; do
                        # extract the tar file
                        # echo "Extracting routinator repository from $file_path"
                        tar -xzvf "$file_path" -C "$region_folder" > /dev/null
                    done < <(find "$region_folder" -type f -name "host.rpki_cache" -print0)
                fi
            fi
        done

    fi
done
echo "Done parsing configs"
