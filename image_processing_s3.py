import subprocess
import time
import sys
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


# raycluster_cmds = {
#     "220Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --skip-mirror  --run-ray',
#     "200Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_200m.json',
#     "150Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_150m.json',
#     "100Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_100m.json',
#     "50Mbits/sec":  'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_50m.json',
#     "30Mbits/sec":  'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_30m.json'
# }

raycluster_cmds = {
    "220": 'python3 setup.py --skip-config-ssh --run-sshuttle --skip-mirror  --run-ray',
    "200": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_200m.json',
    "150": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_150m.json',
    "100": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_100m.json',
    "80": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_80m.json',
    "50":  'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_50m.json',
    "30":  'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_30m.json'
}
if len(sys.argv) > 1:
    bandwidth = sys.argv[1]
    print(f"Running {bandwidth} command")
    
    # Start a new RayCluster with network limitation
    run_cmd('python3 setup.py --skip-config-ssh --shutdown')
    run_cmd(raycluster_cmds[bandwidth])

    time.sleep(5)
    # Delete the data
    run_cmd(f'ssh {cloud_node} rm -rf /home/ec2-user/share/Ray-Workloads/basics/image_tr/task_images_s3')
    run_cmd(f'ssh {head_node} rm -rf /home/ec2-user/share/Ray-Workloads/basics/image_tr/task_images_s3')
    
    run_cmd(f'ssh {head_node} python3 /home/ec2-user/share/Ray-Workloads/basics/image_tr/write_para_s3.py {bandwidth}')

    # Start the our scheduler
    run_cmd(f'ssh {head_node} python3 /home/ec2-user/ray/python/ray/scheduler/init.py', is_blocking=False)
    # run_cmd("ssh {head_node} curl ec2-3-128-201-62.us-east-2.compute.amazonaws.com:8000/get/node-info")
    run_cmd(f"ssh {head_node} curl http://localhost:8000/get/node-info")

    # With Sched
    start_time = time.time()
    run_cmd(f'ssh {head_node} "cd /home/ec2-user/share/Ray-Workloads/basics/image_tr && python3 image_s3.py sched cloud-bursting task_images"')
    total_time = time.time() - start_time
    print(f"bandwidth: Total time with our scheduler: {total_time}")
    # count the file number under task_images folder in cloud node
    print("cloud:")
    run_cmd(f'ssh {cloud_node} ls /home/ec2-user/share/Ray-Workloads/basics/image_tr/task_images_s3 | wc -l', print_output=True)
    print("hpc:")
    run_cmd(f'ssh {head_node} ls /home/ec2-user/share/Ray-Workloads/basics/image_tr/task_images_s3 | wc -l', print_output=True)

    # Without Sched
    run_cmd(f'ssh {cloud_node} rm -rf /home/ec2-user/share/Ray-Workloads/basics/image_tr/task_images_s3')
    run_cmd(f'ssh {head_node} rm -rf /home/ec2-user/share/Ray-Workloads/basics/image_tr/task_images_s3')

    start_time = time.time()
    run_cmd(f'ssh {head_node} "cd /home/ec2-user/share/Ray-Workloads/basics/image_tr && python3 image_s3.py manu cloud-bursting task_images"')
    total_time = time.time() - start_time
    print(f"bandwidth: Total time without our scheduler: {total_time}")
    # count the file number under task_images folder in cloud node
    print("cloud:")
    run_cmd(f'ssh {cloud_node} ls /home/ec2-user/share/Ray-Workloads/basics/image_tr/task_images_s3 | wc -l', print_output=True)
    print("hpc:")
    run_cmd(f'ssh {head_node} ls /home/ec2-user/share/Ray-Workloads/basics/image_tr/task_images_s3 | wc -l', print_output=True)


    print("===============================================")