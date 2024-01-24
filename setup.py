import click
import boto3
import json
import paramiko
import time

# pip3 install sshuttle
# pip3 install ray
# pip3 install ray[client]
# pip3 install ray[default]

config_env_cloud_nodes = ["pip3 install sshuttle", "pip3 install ray", "pip3 install ray[client]", "pip3 install ray[default]"]
config_env_onprem_nodes = ["pip3 install ray", "pip3 install ray[client]", "pip3 install ray[default]"]

def get_ec2_info_from_stack(stack_name):
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
            instances_info.append(instance_info)
    return instances_info

def run_commands_ssh(node_ip, user_name, commands):
    ssh = paramiko.SSHClient()
    try:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=node_ip, username=user_name)
        print("SSH into node: " + node_ip + " successfully")
        for command in commands:
            print("Running command: " + command)
            stdin, stdout, stderr = ssh.exec_command(command)
            print(stdout.read())
            print(stderr.read())
    except Exception as e:
        print("SSH into node: " + node_ip + " failed")
        print(e)
    ssh.close()

def run_commands_ssh_via_login(login_ip, login_user_name, node_ip, user_name, commands):
    # ssh into login node, login node will ssh into other nodes and run commands
    ssh = paramiko.SSHClient()
    try:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=login_ip, username=login_user_name)
        print("SSH into login node: " + login_ip + " successfully")
        for command in commands:
            # execute commands on user_name@node_ip
            stdin, stdout, stderr = ssh.exec_command(f"ssh -o StrictHostKeyChecking=no {user_name}@{node_ip} \"{command}\" ")
            print(stdout.read())
            print(stderr.read())
    except Exception as e:
        print("SSH into login node: " + login_ip + " failed")
        print(e)


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

def setup_env(cluster_info, extra_ssh_keys_list):
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
        add_authorized_keys_ssm(node["InstanceId"], [login_node["SSHPubKey"]])
    for node in onprem_worker_nodes:
        add_authorized_keys_ssm(node["InstanceId"], [login_node["SSHPubKey"]])
    # configure sshuttle on cloud node
    run_commands_ssh(login_node["PublicIp"], "ec2-user", config_env_onprem_nodes)
    for node in cloud_worker_nodes:
        run_commands_ssh(node["PublicIp"], "ec2-user", config_env_cloud_nodes)
    # configure ray environment for all nodes
    for node in onprem_worker_nodes:
        run_commands_ssh_via_login(login_node["PublicIp"], "ec2-user", node["PrivateIp"], "ec2-user", config_env_onprem_nodes)
    # add ssh keys in extra_ssh_keys_list to dev node if it exists
    # don't install ray on dev nodes because we want to build from source code
    if "DevNodesInfo" in cluster_info:
        print("DevNodesInfo found in cluster_info, adding extra ssh keys to dev nodes")
        dev_nodes = cluster_info["DevNodesInfo"]
        assert len(dev_nodes) > 0
        for node in dev_nodes:
            add_authorized_keys_ssm(node["InstanceId"], extra_ssh_keys_list)
    else:
        print("No DevNodesInfo found in cluster_info")

def setup_custom_ray_wheel(cluster_info, custom_ray_wheel):
    # will use the wheel file to overwrite the default installed ray
    pass
        

def convert_command_to_tmux_command(session_name, command):
    return f"tmux new -d -s {session_name} \"{command}\" "

def setup_sshuttle_processes(cluster_info):
    # sshuttle --daemon --dns -NHr ec2-user@login_node_ip <worker nodes>
    onprem_nodes_ips = []
    login_node = None
    for node in cluster_info["OnPremNodesInfo"]:
        onprem_nodes_ips.append(node["PrivateIp"])
        if node["LoginNode"]:
            login_node = node
    onprem_nodes_ips_str = " ".join(onprem_nodes_ips)
    cloud_nodes_ips = []
    for node in cluster_info["CloudNodesInfo"]:
        cloud_nodes_ips.append(node["PublicIp"])
    login_node_ip = login_node["PublicIp"]
    sshuttle_command = f"sshuttle --ssh-cmd 'ssh -o StrictHostKeyChecking=no' --dns -NHr ec2-user@{login_node_ip} {onprem_nodes_ips_str}"
    session_name = "sshuttle_session"
    sshuttle_tmux_command = convert_command_to_tmux_command(session_name, sshuttle_command)
    sshuttle_tmux_commands = [f"tmux kill-session -t {session_name}", sshuttle_tmux_command]
    for node_ip in cloud_nodes_ips:
        print("Running sshuttle command: " + sshuttle_tmux_command)
        run_commands_ssh(node_ip, "ec2-user", sshuttle_tmux_commands)

def setup_ray_processes(cluster_info):
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
    client_server_port = 10001
    min_worker_port = 30010
    max_worker_port = 30050
    num_cpus = 2
    num_gpus = 0
    node_manager_port = 30008
    object_manager_port = 30009
    redis_password = "12345678"
    ray_command_head = f"ray start --head --node-ip-address={login_node_private_ip} --port={gcs_port} --dashboard-port={dashboard_port} --num-cpus {num_cpus} --num-gpus {num_gpus} --ray-client-server-port {client_server_port} --min-worker-port {min_worker_port} --max-worker-port {max_worker_port} --node-manager-port {node_manager_port} --object-manager-port {object_manager_port} --redis-password={redis_password}"
    head_address = f"{login_node_private_ip}:{gcs_port}"
    ray_onprem_worker_commands = []
    for i in range(len(onprem_worker_nodes)):
        node = onprem_worker_nodes[i]
        node_ip = node["PrivateIp"]
        ray_onprem_worker_command = f"ray start --address {head_address} --node-ip-address={node_ip} --num-cpus {num_cpus} --num-gpus {num_gpus} --min-worker-port {min_worker_port} --max-worker-port {max_worker_port} --node-manager-port {node_manager_port} --object-manager-port {object_manager_port} --redis-password={redis_password}"
        ray_onprem_worker_commands.append(ray_onprem_worker_command)
    ray_cloud_worker_commands = []
    for i in range(len(cloud_nodes)):
        node = cloud_nodes[i]
        node_ip = node["PublicIp"]
        ray_cloud_worker_command = f"ray start --address {head_address} --node-ip-address={node_ip} --num-cpus {num_cpus} --num-gpus {num_gpus} --min-worker-port {min_worker_port} --max-worker-port {max_worker_port} --node-manager-port {node_manager_port} --object-manager-port {object_manager_port} --redis-password={redis_password}"
        ray_cloud_worker_commands.append(ray_cloud_worker_command)
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
    print("Ray processes are set up")
    print("Suggestion: Use VSCode remote ssh to get into login node and open up live server to view ray dashboard: http://localhost:8265")
    print("Suggestion: You can also use reverse tunnel to do this with the command below: ")
    print(f"ssh -L 8265:localhost:8265 ec2-user@{login_node_public_ip}")

@click.command()
@click.option('--cluster-config', default='cdk-app-config.json', help='cluster config file, default is cdk-app-config.json')
@click.option('--extra-ssh-keys', default="extra-ssh-keys.json", help='add ssh key to login node and worker nodes by json file')
@click.option('--custom-ray-wheel', default="", help='install self defined ray built from source code, parameter should be an URI')
@click.option('--run-sshuttle', is_flag=True, default=False, help='configure sshuttle')
@click.option('--run-ray', is_flag=True, default=False, help='configure sshuttle and run ray commands')
def main(cluster_config, extra_ssh_keys, custom_ray_wheel, run_sshuttle, run_ray):
    print('Using cluster config file: ' + cluster_config)
    ray_config = None
    with open(cluster_config) as f:
        ray_config = json.load(f)
        # print(ray_config)
    # fill in cluster_info
    cluster_info = {}
    cluster_info["NumCloudNodes"] = ray_config["cloud"]["WORKER_NODE_NUM"]
    cluster_info["NumOnPremNodes"] = ray_config["onprem"]["WORKER_NODE_NUM"] + 1 # add login node itself
    cluster_info["OnPremNodesInfo"] = None
    cluster_info["CloudNodesInfo"] = None
    # fetch node names from cloud formation stack OnPremStack and CloudStack
    on_prem_ec2_info = get_ec2_info_from_stack("OnPremStack")
    cluster_info["OnPremNodesInfo"] = on_prem_ec2_info
    # filter for login node who has public ip
    for node in on_prem_ec2_info:
        if node["PublicIp"] != "":
            node["LoginNode"] = True
        else:
            node["LoginNode"] = False
    print("On Prem Stack Cluster Info: ")
    print(on_prem_ec2_info)
    cloud_ec2_info = get_ec2_info_from_stack("CloudStack")
    cluster_info["CloudNodesInfo"] = cloud_ec2_info
    print("Cloud Stack Cluster Info: ")
    print(cloud_ec2_info)
    # try to find dev stack
    dev_ec2_info = get_ec2_info_from_stack("DevStack")
    if dev_ec2_info is not None:
        cluster_info["DevNodesInfo"] = dev_ec2_info
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
    setup_env(cluster_info, extra_ssh_keys_list)
    if custom_ray_wheel != "":
        print('Setting up custom ray wheel from URL: ' + custom_ray_wheel)
        setup_custom_ray_wheel(cluster_info, custom_ray_wheel)
    # open up long running processes
    if run_ray:
        run_sshuttle = True
    if run_sshuttle:
        print("Running sshuttle on all cloud nodes and tunnel to on prem nodes")
        setup_sshuttle_processes(cluster_info)
    if run_ray:
        print("Running ray commands on all nodes")
        setup_ray_processes(cluster_info)

if __name__ == '__main__':
    main()