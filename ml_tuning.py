import subprocess
import time
import json
# head_node = "3.128.201.62"
# cloud_node = "3.12.146.140"
timeout_duration = 60 * 15


def get_ip():
    # Open the JSON file
    head_ip=''
    cloud_ip=''
    with open('cluster.out.json', 'r') as file:
        # Load the JSON data
        data = json.load(file)

         # Retrieve directory information
        
        OnPremNodesInfo = data['OnPremNodesInfo']
        for node in OnPremNodesInfo:
            if node['PublicIp']!='':
                head_ip=node['PublicIp']
        CloudNodesInfo=data['CloudNodesInfo']
        for node in CloudNodesInfo:
            if node['PublicIp']!='':
                cloud_ip=node['PublicIp']
    return cloud_ip,head_ip

cloud_node,head_node=get_ip()
if head_node=='':
    head_node = "3.128.201.62"
if cloud_node=='':
    cloud_node = "3.12.146.140"






def run_cmd(cmd, is_blocking=True, print_output=False):
    # print("Running command: ", cmd)
    if not is_blocking:
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # subprocess.Popen(cmd, shell=True)
        time.sleep(10)
        return 0
    else:
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout_duration)
            if result.returncode != 0:
                print(cmd, result.stdout, result.stderr, result.returncode)
                exit(1)
            if print_output:
                print(result.stdout, result.stderr)
            return 0
        except subprocess.TimeoutExpired:
            print(f"Command {cmd} timed out after {timeout_duration} seconds")
            return 1

            
raycluster_cmds = {
    # "220Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --skip-mirror  --run-ray',
    # "200Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_200m.json',
    "150Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_150m.json',
    "100Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_100m.json',
    "80Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_80m.json',
    "50Mbits/sec":  'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_50m.json',
    "30Mbits/sec":  'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_30m.json'
}

for bandwidth, raycluster_cmd in raycluster_cmds.items():
    print(f"Running {bandwidth} command")

    # Start a new RayCluster with network limitation
    run_cmd('python3 setup.py --skip-config-ssh --shutdown')
    run_cmd(raycluster_cmd)

    # Delete the data in the cloud nodes
    run_cmd(f'ssh {cloud_node} rm -rf /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch')

    # Start the our scheduler
    run_cmd(f'ssh {head_node} python3 /home/ec2-user/ray/python/ray/scheduler/init.py', is_blocking=False)
    run_cmd(f"ssh {head_node} curl http://localhost:8000/get/node-info")


    start_time = time.time()
    run_cmd(f'ssh {head_node} "cd /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS && python3 ./param-server.py sched"')
    total_time = time.time() - start_time
    print(f"bandwidth: Total time with our scheduler: {total_time}")
    run_cmd(f'ssh {cloud_node} ls /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch | wc -l', print_output=True)

    run_cmd(f'ssh {cloud_node} rm -rf /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch')

    # Start the param server
    start_time = time.time()
    run_cmd(f'ssh {head_node} "cd /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS && python3 param-server.py"')
    total_time = time.time() - start_time
    print(f"bandwidth: Total time without our scheduler: {total_time}")
    run_cmd(f'ssh {cloud_node} ls /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch | wc -l', print_output=True)
