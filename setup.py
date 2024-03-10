import click
import boto3
import json
import paramiko
import time
import os
from networking.netem import NetworkEmulator
from networking.netem import CLOUD, HPC_LOGIN, HPC_WORKER

# pip3 install sshuttle
# pip3 install ray
# pip3 install ray[client]
# pip3 install ray[default]

LOCAL_NODE_TYPE_ONPREM_LOGIN = 0
LOCAL_NODE_TYPE_ONPREM_WORKER = 1
LOCAL_NODE_TYPE_CLOUD = 2

config_watchman_amz_linux_commands = [
    "cd ~ && [ ! -d 'watchman-amazonlinux-problems' ] && git clone https://github.com/marc-guenther/watchman-amazonlinux-problems.git",
    "cd ~/watchman-amazonlinux-problems/watchman && chmod 755 watchman* && sudo mkdir -p /usr/local/bin && sudo cp ./* /usr/local/bin",
]

config_ray_workloads_repo_commands = [
    "cd ~/share && [ ! -d 'Ray-Workloads' ] && git clone https://github.com/HPC-cloud-burst-with-ray/Ray-Workloads.git",
]

config_ray_custom_scheduler_commands = [
    "cd ~ && [ ! -d 'ray' ] && git clone https://github.com/hyoer0423/ray.git",
    "cd ~/ray && git checkout protbuf",
]

config_mirror_commands = [
    "wget https://github.com/stephenh/mirror/releases/latest/download/mirror-all.jar -O ~/mirror-all.jar",
    "wget https://github.com/stephenh/mirror/releases/latest/download/mirror -O ~/mirror",
    "cd ~/ && sudo chmod u+x mirror",
]

check_conda_python310_commands = ["conda --version &> /dev/null && conda env list | grep -q 'myenv' || echo 'FAILED to find conda myenv' "]

config_anaconda_commands = ["cd ~ && curl -O https://repo.anaconda.com/archive/Anaconda3-2023.09-0-Linux-x86_64.sh",
                            # install with default and yes, add to bashrc,
                            "cd ~ && bash ~/Anaconda3-2023.09-0-Linux-x86_64.sh -b -p ~/anaconda3",
                            # init conda and add to bashrc
                            "cd ~ && [ ! -d 'setup_bashrc' ] && git clone https://github.com/HPC-cloud-burst-with-ray/setup_bashrc.git",
                            "cd ~/setup_bashrc && cat add_to_bashrc.txt >> ~/.bashrc",
                            "source ~/.bashrc",
                            ]

config_python310_conda_commands = ["conda create -n myenv python=3.10 -y",
                                   "grep -q 'conda activate myenv' ~/.bashrc || echo 'conda activate myenv' >> ~/.bashrc",
                                   "source ~/.bashrc"]

config_sshuttle_commands = ["pip3 install sshuttle"]

config_official_rayenv_commands = ["pip3 install ray", "pip3 install ray[client]", "pip3 install ray[default]"]

# config_workloads_deps_commands = ["pip install sklearn torch torchvision filelock statsforecast pandas pyarrow aiorwlock requests Pillow boto3"]
config_workloads_deps_commands = ["pip install torch torchvision pandas pycocotools",
                                  "pip install filelock statsforecast pyarrow requests",
                                  "pip install Pillow aiorwlock uvicorn plotly grpcio"]

config_workloads_deps_conflict_commands = ["pip uninstall fastapi pydantic -y", 
                                           "pip install fastapi==0.104.1",
                                           "pip install pydantic==1.8"]


config_custom_ray_wheel_s3_commands = ["pip install boto3", 
                                       "rm -rf ~/host-ray-wheel-asset && cd ~ && git clone https://github.com/HPC-cloud-burst-with-ray/host-ray-wheel-asset.git ~/host-ray-wheel-asset"]

remove_existing_ray_commands = ["pip3 uninstall -y ray"]

shutdown_all_processes_commands = ["ray stop", '''tmux list-sessions | awk -F: '{print $1}' | xargs -I {} tmux kill-session -t {} ''']


def get_num_cpus(instance_info):
    return instance_info["VCpuInfo"]["DefaultVCpus"]

def get_num_gpus(instance_info):
    if instance_info["VGpuInfo"] is None:
        return 0
    return len(instance_info["VGpuInfo"]["Gpus"])

def get_ec2_info_from_stack(stack_name):
    print("Getting EC2 info from stack: " + stack_name)
    cloudformation = boto3.client('cloudformation')
    ec2_client = boto3.client('ec2')
    try:
        response = cloudformation.describe_stack_resources(StackName=stack_name)
    except Exception as e:
        print("Stack: " + stack_name + " does not exist")
        return None
    resource_ids = []
    for resource in response['StackResources']:
        if resource['ResourceType'] == 'AWS::EC2::Instance':
            # print(resource)
            resource_ids.append(resource['PhysicalResourceId'])
    # print(resource_ids)
    instances_info = []
    ec2_response = ec2_client.describe_instances(InstanceIds=resource_ids)
    for reservation in ec2_response['Reservations']:
        for instance in reservation['Instances']:
            instance_info = {}
            # filter through list of tags to find Key == Name
            for tag in instance['Tags']:
                if tag['Key'] == 'Name':
                    instance_info["Name"] = tag['Value']
            instance_info["InstanceId"] = instance['InstanceId']
            instance_info["PublicIp"] = instance.get('PublicIpAddress', "")
            instance_info["PrivateIp"] = instance['PrivateIpAddress']
            # fill in cpu gpu number
            instance_type_name = instance['InstanceType']
            instance_type = ec2_client.describe_instance_types(InstanceTypes=[instance_type_name])
            # print(instance_type['InstanceTypes'][0])
            current_vcpu_info = instance_type['InstanceTypes'][0]['VCpuInfo']
            # current_vcpu_count = instance_type['InstanceTypes'][0]['VCpuInfo']['DefaultVCpus']
            current_vgpu_info = instance_type['InstanceTypes'][0].get('GpuInfo', None)
            # current_vgpu_count = instance_type['InstanceTypes'][0]['GpuInfo']['Gpus']
            instance_info["VCpuInfo"] = current_vcpu_info
            instance_info["VGpuInfo"] = current_vgpu_info
            current_vcpu_count = get_num_cpus(instance_info)
            current_vgpu_info = get_num_gpus(instance_info)
            print("Instance type: " + instance_type_name + " has vcpu count: " + str(current_vcpu_count) + " and gpu count: " + str(current_vgpu_info))
            instances_info.append(instance_info)
    return instances_info

def run_commands_ssh(node_ip, user_name, commands):
    if len(commands) == 0:
        print("No commands to run")
        return
    ssh = paramiko.SSHClient()
    return_output = []
    try:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=node_ip, username=user_name)
        print("SSH into node: " + node_ip + " successfully")
        for command in commands:
            print("Running command: " + command)
            stdin, stdout, stderr = ssh.exec_command(command)
            command_output = stdout.read()
            return_output.append(command_output)
            print(command_output)
            print(stderr.read())
    except Exception as e:
        print("SSH into node: " + node_ip + " failed")
        print(e)
    ssh.close()
    return return_output

def run_commands_ssh_via_login(login_ip, login_user_name, node_ip, user_name, commands):
    if len(commands) == 0:
        print("No commands to run")
        return
    # ssh into login node, login node will ssh into other nodes and run commands
    ssh = paramiko.SSHClient()
    return_output = []
    try:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=login_ip, username=login_user_name)
        print("SSH into login node: " + login_ip + " successfully")
        for command in commands:
            # execute commands on user_name@node_ip
            stdin, stdout, stderr = ssh.exec_command(f"ssh -o StrictHostKeyChecking=no {user_name}@{node_ip} \"{command}\" ")
            command_output = stdout.read()
            return_output.append(command_output)
            print(command_output)
            print(stderr.read())
    except Exception as e:
        print("SSH into login node: " + login_ip + " failed")
        print(e)
    ssh.close()
    return return_output

def add_authorized_keys_ssm(instance_id, ssh_keys_to_add):
    ssm = boto3.client('ssm')
    try:
        # avoid adding duplicate ssh keys, also execute under ec2-user
        grep_commands = [f"sudo su - ec2-user -c \"grep '{key}' ~/.ssh/authorized_keys \" " for key in ssh_keys_to_add]
        echo_commands = [f"sudo su - ec2-user -c \"echo '{key}' >> ~/.ssh/authorized_keys \" " for key in ssh_keys_to_add]
        for i in range(len(grep_commands)):
            # grep_command = grep_commands[i]
            grep_command = grep_commands[i]
            print(grep_command)
            echo_command = echo_commands[i]
            response = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={'commands': [grep_command]}
            )
            command_id = response['Command']['CommandId']
            # wait for command to finish
            time.sleep(3)
            # get command output
            response = ssm.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id
            )
            if response['Status'] == 'Success':
                print("SSH key: " + ssh_keys_to_add[i] + " already exists in authorized_keys")
            else:
                response = ssm.send_command(
                    InstanceIds=[instance_id],
                    DocumentName="AWS-RunShellScript",
                    Parameters={'commands': [echo_command]}
                )
                command_id = response['Command']['CommandId']
                # wait for command to finish
                time.sleep(3)
                # get command output
                response = ssm.get_command_invocation(
                    CommandId=command_id,
                    InstanceId=instance_id
                )
                if response['Status'] == 'Success':
                    print("Adding ssh key: " + ssh_keys_to_add[i] + " to authorized_keys")
                else:
                    print("Adding ssh key: " + ssh_keys_to_add[i] + " to authorized_keys failed")
                # print(response)
    except Exception as e:
        print("Adding ssh key to on prem node: " + instance_id + " failed")
        print(e)

def setup_ssh_auth_keys(cluster_info, extra_ssh_keys_list):
    ssm = boto3.client('ssm')
    # get login node, on prem worker nodes, and cloud worker nodes
    login_node = None
    onprem_worker_nodes = []
    cloud_worker_nodes = []
    for node in cluster_info["OnPremNodesInfo"]:
        if node["LoginNode"]:
            login_node = node
        else:
            onprem_worker_nodes.append(node)
    cloud_worker_nodes = cluster_info["CloudNodesInfo"]
    # configure ssh keys
    ssh_pub_login = ssm.get_parameter(Name='/sshkey/onprem/loginNode/id_rsa_pub')
    # print(ssh_pub_login)
    login_node["SSHPubKey"] = ssh_pub_login['Parameter']['Value']
    cloud_worker_nodes.sort(key=lambda x: x["Name"])
    node_index = 0
    for node in cloud_worker_nodes:
        # pad node_index to two digits
        node_index_str = str(node_index)
        if node_index < 10:
            node_index_str = "0" + node_index_str
        parameter_url = '/sshkey/cloud/cloudNode' + node_index_str + '/id_rsa_pub'
        ssh_pub_cloud = ssm.get_parameter(Name=parameter_url)
        node["SSHPubKey"] = ssh_pub_cloud['Parameter']['Value']
        print("Finding ssh key for node: " + node["Name"] + " with parameter url: " + parameter_url)
        print("ssh key: " + node["SSHPubKey"])
        node_index += 1
    # get into login node and setup ssh authorized keys for cloud nodes
    ssh_keys_to_add = []
    for node in cloud_worker_nodes:
        ssh_keys_to_add.append(node["SSHPubKey"])
    ssh_keys_to_add.extend(extra_ssh_keys_list)
    add_authorized_keys_ssm(login_node["InstanceId"], ssh_keys_to_add)
    # give public key of login node to all other nodes to enable ssh connection into all other nodes
    for node in cloud_worker_nodes:
        add_authorized_keys_ssm(node["InstanceId"], [login_node["SSHPubKey"]] + extra_ssh_keys_list)
    for node in onprem_worker_nodes:
        add_authorized_keys_ssm(node["InstanceId"], [login_node["SSHPubKey"]])
    # also config ssh keys for dev node
    if "DevNodesInfo" in cluster_info:
        print("DevNodesInfo found in cluster_info, adding extra ssh keys to dev nodes")
        dev_nodes = cluster_info["DevNodesInfo"]
        assert len(dev_nodes) > 0
        for node in dev_nodes:
            add_authorized_keys_ssm(node["InstanceId"], extra_ssh_keys_list)
    else:
        print("No DevNodesInfo found in cluster_info")


def install_custom_ray_wheel(login_node, onprem_worker_nodes, cloud_worker_nodes, custom_ray_wheel):
    # will use the wheel file to overwrite the default installed ray
    # check if URL is http or s3
    # http example: http://23.21.12.11:8888/ray-3.0.0.dev0-cp310-cp310-linux_x86_64.whl
    # s3 example: s3://wheelbucket/ray-3.0.0.dev0-cp310-cp310-linux_x86_64.whl 
    # login node cd into ~/share, curl to download, let NFS share to other nodes
    login_node_ip = login_node["PublicIp"]
    login_node_user = "ec2-user"
    login_node_share_dir = "~/share"
    # cloud nodes
    cloud_node = cloud_worker_nodes[0]
    cloud_node_ip = cloud_node["PublicIp"]
    cloud_node_user = "ec2-user"
    cloud_node_share_dir = "~/share"
    # filename
    filename = custom_ray_wheel.split('/')[-1]
    if custom_ray_wheel.startswith("http"):
        curl_command = f"curl -o {filename} {custom_ray_wheel}"
        run_commands_ssh(login_node_ip, login_node_user, [f"cd {login_node_share_dir} && {curl_command}"])
        run_commands_ssh(cloud_node_ip, cloud_node_user, [f"cd {cloud_node_share_dir} && {curl_command}"])
        time.sleep(15)
    elif custom_ray_wheel.startswith("s3"):
        # download from s3, will support later
        run_commands_ssh(login_node_ip, login_node_user, config_custom_ray_wheel_s3_commands)
        run_commands_ssh(cloud_node_ip, cloud_node_user, config_custom_ray_wheel_s3_commands)
        download_s3_command_login = f"cd ~/host-ray-wheel-asset && python3 download_s3.py {custom_ray_wheel} {login_node_share_dir}"
        download_s3_command_cloud = f"cd ~/host-ray-wheel-asset && python3 download_s3.py {custom_ray_wheel} {login_node_share_dir}"
        run_commands_ssh(login_node_ip, login_node_user, [download_s3_command_login])
        run_commands_ssh(cloud_node_ip, cloud_node_user, [download_s3_command_cloud])
        time.sleep(15)
    # begin to install by ray wheel
    force_reinstall_flag = " "
    run_commands_ssh(login_node_ip, login_node_user, [f"cd {login_node_share_dir} && pip3 install {force_reinstall_flag} ./{filename}"])
    for node in onprem_worker_nodes:
        run_commands_ssh_via_login(login_node_ip, login_node_user, node["PrivateIp"], "ec2-user", [f"cd {login_node_share_dir} && pip3 install {force_reinstall_flag} ./{filename}"])
    for node in cloud_worker_nodes:
        run_commands_ssh(node["PublicIp"], "ec2-user", [f"cd {cloud_node_share_dir} && pip3 install {force_reinstall_flag} ./{filename}"])

def check_and_config_conda(node, login_node):
    need_to_config_conda = False
    if login_node is None:
        check_result = run_commands_ssh(node["PublicIp"], "ec2-user", check_conda_python310_commands)[0].decode("utf-8")
        if "FAILED" in check_result:
            need_to_config_conda = True
    else:
        check_result = run_commands_ssh_via_login(login_node["PublicIp"], "ec2-user", node["PrivateIp"], "ec2-user", check_conda_python310_commands)[0].decode("utf-8")
        if "FAILED" in check_result:
            need_to_config_conda = True
    if need_to_config_conda:
        print("Need to configure conda for node: " + node["Name"])
        # transfer the local add_to_bashrc.txt to remote nodes
        if not os.path.exists("add_to_bashrc.txt"):
            raise Exception("add_to_bashrc.txt not found")
        if login_node is None:
            run_commands_ssh(node["PublicIp"], "ec2-user", config_anaconda_commands)
            run_commands_ssh(node["PublicIp"], "ec2-user", config_python310_conda_commands)
        else:
            run_commands_ssh_via_login(login_node["PublicIp"], "ec2-user", node["PrivateIp"], "ec2-user", config_anaconda_commands)
            run_commands_ssh_via_login(login_node["PublicIp"], "ec2-user", node["PrivateIp"], "ec2-user", config_python310_conda_commands)
    else:
        print("Conda already configured for node: " + node["Name"])

# print('Setting up custom ray wheel from URL: ' + custom_ray_wheel)
def setup_software_deps(cluster_info, remove_existing_ray, install_all_deps, custom_ray_wheel, install_workload_deps):
    login_node = None
    onprem_worker_nodes = []
    cloud_worker_nodes = []
    for node in cluster_info["OnPremNodesInfo"]:
        if node["LoginNode"]:
            login_node = node
        else:
            onprem_worker_nodes.append(node)
    cloud_worker_nodes = cluster_info["CloudNodesInfo"]
    # check for conda installation and python 3.10 (hard requirement for our workloads)
    print("Checking and configuring conda and python 3.10")
    check_and_config_conda(login_node, None)
    for node in onprem_worker_nodes:
        check_and_config_conda(node, login_node)
    for node in cloud_worker_nodes:
        check_and_config_conda(node, None)
    if remove_existing_ray:
        # raise Exception("remove_existing_ray is not supported during testing")
        run_commands_ssh(login_node["PublicIp"], "ec2-user", remove_existing_ray_commands)
        for node in onprem_worker_nodes:
            run_commands_ssh_via_login(login_node["PublicIp"], "ec2-user", node["PrivateIp"], "ec2-user", remove_existing_ray_commands)
        for node in cloud_worker_nodes:
            run_commands_ssh(node["PublicIp"], "ec2-user", remove_existing_ray_commands)
    # configure software deps by generating pip commands
    config_commands_onprem = []
    config_commands_cloud = []
    config_mirror_all_commands = config_watchman_amz_linux_commands + config_mirror_commands
    config_code_repos_commands = config_ray_workloads_repo_commands + config_ray_custom_scheduler_commands
    config_workloads_all_deps_commands = config_mirror_all_commands + config_workloads_deps_commands
    config_rayenv_commands = []
    patch_fastapi_pydantic_versions = config_workloads_deps_conflict_commands
    use_official_ray = custom_ray_wheel == ""
    if use_official_ray:
        config_rayenv_commands = config_official_rayenv_commands
        if install_all_deps:
            patch_fastapi_pydantic_versions = []
    else:
        # setup by wheel
        install_custom_ray_wheel(login_node, onprem_worker_nodes, cloud_worker_nodes, custom_ray_wheel)
    if install_all_deps:
        config_commands_onprem = config_rayenv_commands + config_workloads_all_deps_commands + patch_fastapi_pydantic_versions
        config_commands_cloud = config_sshuttle_commands + config_rayenv_commands + config_workloads_all_deps_commands + patch_fastapi_pydantic_versions
    elif install_workload_deps:
        config_commands_onprem = config_workloads_all_deps_commands + patch_fastapi_pydantic_versions
        config_commands_cloud = config_sshuttle_commands + config_workloads_all_deps_commands + patch_fastapi_pydantic_versions
    run_commands_ssh(login_node["PublicIp"], "ec2-user", config_commands_onprem + config_code_repos_commands)
    cloud_node_idx = 0
    for node in cloud_worker_nodes:
        run_commands_ssh(node["PublicIp"], "ec2-user", config_commands_cloud)
        if cloud_node_idx == 0:
            run_commands_ssh(node["PublicIp"], "ec2-user", config_ray_workloads_repo_commands)
        cloud_node_idx += 1
    # configure ray environment for all nodes
    for node in onprem_worker_nodes:
        run_commands_ssh_via_login(login_node["PublicIp"], "ec2-user", node["PrivateIp"], "ec2-user", config_commands_onprem)

def convert_command_to_tmux_command(session_name, command):
    return f"tmux new -d -s {session_name} \"{command}\" "

def setup_sshuttle_processes(cluster_info):
    onprem_nodes_ips = []
    login_node = None
    for node in cluster_info["OnPremNodesInfo"]:
        onprem_nodes_ips.append(node["PrivateIp"] + "/32")
        if node["LoginNode"]:
            login_node = node
    onprem_nodes_ips_str = " ".join(onprem_nodes_ips)
    cloud_nodes_ips = []
    for node in cluster_info["CloudNodesInfo"]:
        cloud_nodes_ips.append(node["PublicIp"])
    login_node_ip = login_node["PublicIp"]
    sshuttle_command = f"sshuttle --ssh-cmd 'ssh -o StrictHostKeyChecking=no' --verbose -NHr ec2-user@{login_node_ip} {onprem_nodes_ips_str}"
    session_name = "sshuttle_session"
    sshuttle_tmux_command = convert_command_to_tmux_command(session_name, sshuttle_command)
    sshuttle_tmux_commands = [f"tmux kill-session -t {session_name}", sshuttle_tmux_command]
    for node_ip in cloud_nodes_ips:
        # print("Running sshuttle command: " + sshuttle_tmux_command)
        run_commands_ssh(node_ip, "ec2-user", sshuttle_tmux_commands)

def get_tc_netem_links(cluster_info, node_name_map):
    login_node = None
    onprem_worker_nodes = []
    cloud_worker_nodes = []
    for node in cluster_info["OnPremNodesInfo"]:
        if node["LoginNode"]:
            login_node = node
        else:
            onprem_worker_nodes.append(node)
    cloud_worker_nodes = cluster_info["CloudNodesInfo"]
    # return format: map{ src_node -> [(dst_01, LABEL), (dst_02, LABEL)]}
    login_node["NetEmLabel"] = HPC_LOGIN
    for node in onprem_worker_nodes:
        node["NetEmLabel"] = HPC_WORKER
    for node in cloud_worker_nodes:
        node["NetEmLabel"] = CLOUD
    netem_links = {}
    netem_links[login_node["Name"]] = []
    for node in onprem_worker_nodes:
        netem_links[login_node["Name"]].append(node["Name"])
        netem_links[node["Name"]] = [login_node["Name"]]
    for node in cloud_worker_nodes:
        netem_links[login_node["Name"]].append(node["Name"])
        netem_links[node["Name"]] = [login_node["Name"]]
    # mutal links between onprem and cloud nodes
    if len(onprem_worker_nodes) > 1:
        for node in onprem_worker_nodes:
            other_nodes_names = [x["Name"] for x in onprem_worker_nodes]
            other_nodes_names.remove(node["Name"])
            netem_links[node["Name"]].extend(other_nodes_names["Name"])
    print(netem_links)
    return netem_links

def get_target_ip(src_node, dst_node):
    target_ip = None
    edge = (src_node["NetEmLabel"], dst_node["NetEmLabel"])
    if edge[0] == HPC_LOGIN:
        if edge[1] == HPC_LOGIN:
            pass
        elif edge[1] == HPC_WORKER:
            target_ip = dst_node["PrivateIp"]
        elif edge[1] == CLOUD:
            target_ip = dst_node["PublicIp"]
    elif edge[0] == HPC_WORKER:
        if edge[1] == HPC_LOGIN:
            target_ip = dst_node["PrivateIp"]
        elif edge[1] == HPC_WORKER:
            target_ip = dst_node["PrivateIp"]
        elif edge[1] == CLOUD:
            target_ip = dst_node["PublicIp"]
    elif edge[0] == CLOUD:
        if edge[1] == HPC_LOGIN:
            target_ip = dst_node["PublicIp"]
        elif edge[1] == HPC_WORKER:
            pass
        elif edge[1] == CLOUD:
            pass
    return target_ip

def dump_tc_commands_map_to_json(commands_map, json_file_name):
    # for each key of the map, only dump the "Name" field
    output_map = {}
    for key, value in commands_map.items():
        output_map[key] = value
    with open(json_file_name, "w") as file:
        json.dump(output_map, file, indent=4)

def setup_tc_network_emulator(cluster_info, node_name_map, netem):
    # setup tc commands in each node
    netem_links = get_tc_netem_links(cluster_info, node_name_map)
    # loop over the map to generate tc commands
    device = "ens5"
    commands_map = {}
    for src_node_name, dst_nodes_names in netem_links.items():
        node_outbound_link_id = 1
        disable_tc_commands = netem.get_netem_disable_commands(device)
        commands_map[src_node_name] = disable_tc_commands
        dst_nodes = [node_name_map[x] for x in dst_nodes_names]
        src_node = node_name_map[src_node_name]
        for dst_node in dst_nodes:
            edge = (src_node["NetEmLabel"], dst_node["NetEmLabel"])
            # skip login to hpc worker and hpc worker to login
            if edge == (HPC_LOGIN, HPC_WORKER) or edge == (HPC_WORKER, HPC_LOGIN):
                print("Skipping tc commands for edge: " + str(edge))
                continue
            # get network tc commands
            target_ip = get_target_ip(src_node, dst_node)
            assert target_ip is not None
            tc_commands = netem.get_netem_setup_commands(edge, device, target_ip, node_outbound_link_id)
            node_outbound_link_id += 1
            # extend the commands to run
            commands_map[src_node_name].extend(tc_commands)
    # dump commands map to json
    dump_tc_commands_map_to_json(commands_map, "setup_tc_commands_map.json")
    # run tc commands on each node
    print("Running tc commands on each node")
    login_node = None
    for node in cluster_info["OnPremNodesInfo"]:
        if node["LoginNode"]:
            login_node = node
    for node_name, commands in commands_map.items():
        node = node_name_map[node_name]
        print("Running tc commands for node: " + node_name)
        if node.get("PublicIp") is not None and node.get("PublicIp") != "":
            run_commands_ssh(node["PublicIp"], "ec2-user", commands)
            # print("commands for node: " + node["Name"])
        else:
            run_commands_ssh_via_login(login_node["PublicIp"], "ec2-user", node["PrivateIp"], "ec2-user", commands)
            # print("commands for node: " + node["Name"])
    
    

def destroy_tc_network_emulator(cluster_info, node_name_map, netem):
    netem_links = get_tc_netem_links(cluster_info, node_name_map)
    # loop over the map to generate tc commands
    device = "ens5"
    commands_map = {}
    for src_node_name in netem_links.keys():
        src_node = node_name_map[src_node_name]
        disable_tc_commands = netem.get_netem_disable_commands(device)
        commands_map[src_node_name] = disable_tc_commands
    # dump commands map to json
    dump_tc_commands_map_to_json(commands_map, "destroy_tc_commands_map.json")
    # run tc commands on each node
    print("Running tc commands on each node")
    login_node = None
    for node in cluster_info["OnPremNodesInfo"]:
        if node["LoginNode"]:
            login_node = node
    for node_name, commands in commands_map.items():
        node = node_name_map[node_name]
        print("Running tc commands for node: " + node_name)
        if node.get("PublicIp") is not None and node.get("PublicIp") != "":
            run_commands_ssh(node["PublicIp"], "ec2-user", commands)
            # print("commands for node: " + node["Name"])
        else:
            run_commands_ssh_via_login(login_node["PublicIp"], "ec2-user", node["PrivateIp"], "ec2-user", commands)
            # print("commands for node: " + node["Name"])


def setup_ray_processes(cluster_info, skip_mirror):
    onprem_nodes = cluster_info["OnPremNodesInfo"]
    onprem_worker_nodes = []
    login_node = None
    cloud_nodes = cluster_info["CloudNodesInfo"]
    for node in onprem_nodes:
        if not node["LoginNode"]:
            onprem_worker_nodes.append(node)
        else:
            login_node = node
    login_node_private_ip = login_node["PrivateIp"]
    login_node_public_ip = login_node["PublicIp"]
    gcs_port = 6379
    dashboard_port = 8265
    # client_server_port = 10001
    min_worker_port = 30010
    max_worker_port = 30090
    # num_cpus = 2
    # num_gpus = 0
    # test what if we don't run workloads in head node, set num_cpus to 1 (one process for shceduler)
    # num_cpu_head = get_num_cpus(login_node)
    num_cpu_head = 2
    num_gpu_head = get_num_gpus(login_node)
    print("Num CPU on login node: " + str(num_cpu_head))
    print("Num GPU on login node: " + str(get_num_gpus(login_node)))
    node_manager_port = 30008
    object_manager_port = 30009
    redis_password = "12345678"
    ray_command_head = f"ray start --head --node-ip-address={login_node_private_ip} --port={gcs_port} --dashboard-port={dashboard_port} --num-cpus {num_cpu_head} --num-gpus {num_gpu_head}  --min-worker-port {min_worker_port} --max-worker-port {max_worker_port} --node-manager-port {node_manager_port} --object-manager-port {object_manager_port} --redis-password={redis_password}"
    head_address = f"{login_node_private_ip}:{gcs_port}"
    ray_onprem_worker_commands = []
    for i in range(len(onprem_worker_nodes)):
        node = onprem_worker_nodes[i]
        node_ip = node["PrivateIp"]
        num_cpu_onprem_worker = get_num_cpus(node)
        num_gpu_onprem_worker = get_num_gpus(node)
        print("Num CPU on onprem worker node: " + str(num_cpu_onprem_worker))
        print("Num GPU on onprem worker node: " + str(num_gpu_onprem_worker))
        ray_onprem_worker_command = f"ray start --address {head_address} --node-ip-address={node_ip} --num-cpus {num_cpu_onprem_worker} --num-gpus {num_gpu_onprem_worker} --min-worker-port {min_worker_port} --max-worker-port {max_worker_port} --node-manager-port {node_manager_port} --object-manager-port {object_manager_port} --redis-password={redis_password}"
        ray_onprem_worker_commands.append(ray_onprem_worker_command)
    ray_cloud_worker_commands = []
    for i in range(len(cloud_nodes)):
        node = cloud_nodes[i]
        node_ip = node["PublicIp"]
        num_cpu_cloud_worker = get_num_cpus(node)
        num_gpu_cloud_worker = get_num_gpus(node)
        print("Num CPU on cloud worker node: " + str(num_cpu_cloud_worker))
        print("Num GPU on cloud worker node: " + str(num_gpu_cloud_worker))
        ray_cloud_worker_command = f"ray start --address {head_address} --node-ip-address={node_ip} --num-cpus {num_cpu_cloud_worker} --num-gpus {num_gpu_cloud_worker} --min-worker-port {min_worker_port} --max-worker-port {max_worker_port} --node-manager-port {node_manager_port} --object-manager-port {object_manager_port} --redis-password={redis_password}"
        ray_cloud_worker_commands.append(ray_cloud_worker_command)
    # set environment variable for ray: HEAD_NODE_IP = login node private ip
    set_head_ip_bashrc_command = f"grep -q 'HEAD_NODE_IP' ~/.bashrc || echo 'export HEAD_NODE_IP={login_node_private_ip}' >> ~/.bashrc"
    set_local_node_onprem_login_bashrc_command = f"grep -q 'LOCAL_NODE_TYPE' ~/.bashrc || echo 'export LOCAL_NODE_TYPE={LOCAL_NODE_TYPE_ONPREM_LOGIN}' >> ~/.bashrc"
    set_local_node_onprem_worker_bashrc_command = f"grep -q 'LOCAL_NODE_TYPE' ~/.bashrc || echo 'export LOCAL_NODE_TYPE={LOCAL_NODE_TYPE_ONPREM_WORKER}' >> ~/.bashrc"
    set_local_node_cloud_bashrc_command = f"grep -q 'LOCAL_NODE_TYPE' ~/.bashrc || echo 'export LOCAL_NODE_TYPE={LOCAL_NODE_TYPE_CLOUD}' >> ~/.bashrc"
    set_login_bashrc_commands = [set_head_ip_bashrc_command, set_local_node_onprem_login_bashrc_command, "source ~/.bashrc"]
    set_onprem_worker_bashrc_commands = [set_local_node_onprem_worker_bashrc_command, "source ~/.bashrc"]
    set_cloud_bashrc_commands = [set_local_node_cloud_bashrc_command, "source ~/.bashrc"]
    # try to save this environment variable to ~/.bashrc if not already there
    run_commands_ssh(login_node["PublicIp"], "ec2-user", set_login_bashrc_commands)
    for node in onprem_worker_nodes:
        run_commands_ssh_via_login(login_node["PublicIp"], "ec2-user", node["PrivateIp"], "ec2-user", set_onprem_worker_bashrc_commands)
    for node in cloud_nodes:
        run_commands_ssh(node["PublicIp"], "ec2-user", set_cloud_bashrc_commands)
    # start to close all previous ray processes
    run_commands_ssh(login_node["PublicIp"], "ec2-user", ["ray stop"])
    for node in onprem_worker_nodes:
        run_commands_ssh_via_login(login_node["PublicIp"], "ec2-user", node["PrivateIp"], "ec2-user", ["ray stop"])
    for node in cloud_nodes:
        run_commands_ssh(node["PublicIp"], "ec2-user", ["ray stop"])
    # start new ray processes
    run_commands_ssh(login_node["PublicIp"], "ec2-user", [ray_command_head])
    for i in range(len(onprem_worker_nodes)):
        node = onprem_worker_nodes[i]
        run_commands_ssh_via_login(login_node["PublicIp"], "ec2-user", node["PrivateIp"], "ec2-user", [ray_onprem_worker_commands[i]])
    for i in range(len(cloud_nodes)):
        node = cloud_nodes[i]
        run_commands_ssh(node["PublicIp"], "ec2-user", [ray_cloud_worker_commands[i]])
    # finishing setting up ray processes
    print("Ray processes are set up, setting up unified distributed file system through mirror")
    # setup mirror process
    if skip_mirror:
        print("Skipping running mirror processes")
    else:
        login_node_share_dir = "~/share"
        cloud_node_share_dir = "~/share"
        mirror_server_command = "cd ~ && ./mirror server --skip-limit-checks"
        mirror_client_command = f"cd ~ && ./mirror client -h {login_node_private_ip} -l {login_node_share_dir} -r {cloud_node_share_dir} --skip-limit-checks"
        mirror_tmux_session_name = "mirror_session"
        run_commands_ssh(login_node["PublicIp"], "ec2-user", [f"tmux kill-session -t {mirror_tmux_session_name}", convert_command_to_tmux_command(mirror_tmux_session_name, mirror_server_command)])
        run_commands_ssh(cloud_nodes[0]["PublicIp"], "ec2-user", [f"tmux kill-session -t {mirror_tmux_session_name}", convert_command_to_tmux_command(mirror_tmux_session_name, mirror_client_command)])
    print("Suggestion: Use VSCode remote ssh to get into login node and open up live server to view ray dashboard: http://localhost:8265")
    print("Suggestion: You can also use reverse tunnel to do this with the command below: ")
    print(f"ssh -L 8265:localhost:8265 ec2-user@{login_node_public_ip}")

@click.command()
# cluster config file about nodes and ssh keys, etc.
@click.option('--cluster-config', default='cdk-app-config.json', help='cluster config file, default is cdk-app-config.json')
# ssh options
@click.option('--skip-config-ssh', is_flag=True, default=False, help='skip configuring ssh, because they are already configured')
@click.option('--extra-ssh-keys', default="extra-ssh-keys.json", help='add ssh key to login node and worker nodes by json file')
# specify network topology file path
@click.option('--network-topology', default="network_topology.json", help='network topology file path for tc netem configuration')
# environment options, whether to install, remove or use custom wheel
@click.option('--remove-existing-ray', is_flag=True, default=False, help='remove existing ray installation')
@click.option('--install-all-deps', is_flag=True, default=False, help='install official ray, sshuttle, watchman, mirror and other dependencies')
@click.option('--custom-ray-wheel', default="", help='install self defined ray built from source code, parameter should be an URI to curl from or a S3 URL')
# environment for running ray workloads
@click.option('--install-workload-deps', is_flag=True, default=False, help='install software deps for ray workloads only')
# whether to run network auto-configuration
@click.option('--run-sshuttle', is_flag=True, default=False, help='configure sshuttle')
@click.option('--skip-mirror', is_flag=True, default=False, help='skip running mirror processes')
@click.option('--run-tc-netem', is_flag=True, default=False, help='configure tc netem on all nodes to simulate network conditions')
# run ray start commands
@click.option('--run-ray', is_flag=True, default=False, help='configure sshuttle and run ray commands')
@click.option('--shutdown', is_flag=True, default=False, help='shutdown all nodes ray processes and networking processes')
def main(cluster_config, skip_config_ssh, extra_ssh_keys, network_topology, remove_existing_ray, install_all_deps, custom_ray_wheel, install_workload_deps, run_sshuttle, skip_mirror, run_tc_netem, run_ray, shutdown):
    print('Using cluster config file: ' + cluster_config)
    ray_config = None
    with open(cluster_config) as f:
        ray_config = json.load(f)
        # print(ray_config)
    # fill in cluster_info
    if shutdown:
        print("Shutting down all nodes ray processes and networking processes, disable the run flags")
        run_sshuttle = False
        run_ray = False
        run_tc_netem = False
    cluster_info = {}
    cluster_info["NumCloudNodes"] = ray_config["cloud"]["WORKER_NODE_NUM"]
    cluster_info["NumOnPremNodes"] = ray_config["onprem"]["WORKER_NODE_NUM"] + 1 # add login node itself
    cluster_info["OnPremNodesInfo"] = None
    cluster_info["CloudNodesInfo"] = None
    # fetch node names from cloud formation stack OnPremStack and CloudStack
    on_prem_ec2_info = get_ec2_info_from_stack("OnPremStack")
    cluster_info["OnPremNodesInfo"] = on_prem_ec2_info
    # register nodes by name
    node_name_map = {}
    def register_node(node):
        nonlocal node_name_map
        node_name_map[node["Name"]] = node
    login_node = None
    # filter for login node who has public ip
    for node in on_prem_ec2_info:
        register_node(node)
        if node["PublicIp"] != "":
            node["LoginNode"] = True
            login_node = node
        else:
            node["LoginNode"] = False
    print("On Prem Stack Cluster Info: ")
    print(on_prem_ec2_info)
    cloud_ec2_info = get_ec2_info_from_stack("CloudStack")
    cluster_info["CloudNodesInfo"] = cloud_ec2_info
    for node in cloud_ec2_info:
        register_node(node)
    print("Cloud Stack Cluster Info: ")
    print(cloud_ec2_info)
    # try to find dev stack
    dev_ec2_info = get_ec2_info_from_stack("DevStack")
    if dev_ec2_info is not None:
        cluster_info["DevNodesInfo"] = dev_ec2_info
        for node in dev_ec2_info:
            register_node(node)
        print("Dev Stack Cluster Info: ")
        print(dev_ec2_info)
    # dump cluster_info to file for users to review
    with open('cluster.out.json', 'w') as outfile:
        json.dump(cluster_info, outfile)
    print('Setting up SSH')
    extra_ssh_keys_list = []
    if extra_ssh_keys is not None:
        print('Adding extra ssh keys')
        with open(extra_ssh_keys) as f:
            extra_ssh_keys_kv = json.load(f)["sshkeys"]
            for obj in extra_ssh_keys_kv:
                print("recognizing ssh key with name: " + obj["name"])
                extra_ssh_keys_list.append(obj["key"])
    if not skip_config_ssh:
        setup_ssh_auth_keys(cluster_info, extra_ssh_keys_list)
    # software deps
    setup_software_deps(cluster_info, remove_existing_ray, install_all_deps, custom_ray_wheel, install_workload_deps)
    # auto open sshuttle if running ray (comment out if sshuttle needs to be run manually)
    # if run_ray:
    #     run_sshuttle = True
    if run_sshuttle:
        print("Running sshuttle on all cloud nodes and tunnel to on prem nodes")
        setup_sshuttle_processes(cluster_info)
    else:
        print("Not running sshuttle by script, assume sshuttle is already running by manual commands if further steps need it")
    if run_tc_netem:
        print("Running tc netem on cloud nodes and HPC nodes to simulate network conditions")
        try:
            netem = NetworkEmulator(network_topology)
        except Exception as e:
            print(f"Failed to read default network topology file: {network_topology}")
            print(e)
            return
        setup_tc_network_emulator(cluster_info, node_name_map, netem)
    if run_ray:
        print("Running ray commands on all nodes")
        setup_ray_processes(cluster_info, skip_mirror)
    if shutdown:
        print("Closing all network emulation by tc")
        try:
            netem = NetworkEmulator(network_topology)
            destroy_tc_network_emulator(cluster_info, node_name_map, netem)
        except Exception as e:
            print(f"Failed to read default network topology file: {network_topology}")
            print(e)
            return
        print("Shutting down all nodes ray processes and networking processes")
        for node in cloud_ec2_info:
            run_commands_ssh(node["PublicIp"], "ec2-user", shutdown_all_processes_commands)
        for node in on_prem_ec2_info:
            if not node["LoginNode"]:
                run_commands_ssh_via_login(login_node["PublicIp"], "ec2-user", node["PrivateIp"], "ec2-user", shutdown_all_processes_commands)
            else:
                run_commands_ssh(node["PublicIp"], "ec2-user", shutdown_all_processes_commands)
        print("Finished shutting down all nodes ray processes and networking processes! Bye~")

if __name__ == '__main__':
    main()