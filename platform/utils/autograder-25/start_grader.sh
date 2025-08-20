# # if gitlab_configs_copy folder exist, remove and re-copy it
# if [ -d "gitlab_configs_copy" ]; then
#   sudo rm -rf gitlab_configs_copy
# fi
# cp -r gitlab_configs gitlab_configs_copy

# take the asn file as input
asn_file=$1
python3 grader.py $asn_file

