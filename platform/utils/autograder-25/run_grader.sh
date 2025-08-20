#!/bin/bash
# cd /home/yuchen/mini_internet_project/platform/grader
# sudo rm -rf ./gitlab_configs
# scp -r -q duvel:/home/yuchen/gitlab_configs/ ./
# # sudo rm -r ./saved_config
# # ssh duvel "sudo ./dump_configs.sh"
# # rsync -az duvel:/home/yuchen/saved_config/ ./saved_config/
# # ssh duvel "sudo rm -r saved_config"

# # # get required files from duvel
# rsync -az duvel:/home/alex/mini_internet_project/platform/groups/rpki/root.crt ./root.crt
# rsync -az duvel:/home/alex/mini_internet_project/platform/groups/rpki/tals ./
# rsync -az duvel:/home/alex/mini_internet_project/platform/groups/g1/rpki_exceptions.json ./rpki_exceptions.json
# rsync -az duvel:/home/alex/mini_internet_project/platform/config/aslevel_links_students.txt ./aslevel_links_students.txt
# sudo env "PATH=$PATH" python grader.py asn_all.txt
