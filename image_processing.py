import subprocess
import time
head_node = "3.128.201.62"
cloud_node = "3.12.146.140"
timeout_duration = 60 * 15

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
    "220Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --skip-mirror  --run-ray',
    "200Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_200m.json',
    "150Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_150m.json',
    "100Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_100m.json',
    "80Mbits/sec": 'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_80m.json',
    "50Mbits/sec":  'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_50m.json',
    "30Mbits/sec":  'python3 setup.py --skip-config-ssh --run-sshuttle --run-tc-netem --skip-mirror --run-ray  --network-topology network_topology_30m.json'
}
keys = [
    "220Mbits/sec", 
    "200Mbits/sec", 
    "150Mbits/sec", 
    "100Mbits/sec", 
    "80Mbits/sec", 
    "50Mbits/sec", 
    "30Mbits/sec"
]
idx = 2

while idx < len(keys):
    bandwidth = keys[idx]
    raycluster_cmd = raycluster_cmds[bandwidth]

    print(f"Running {bandwidth} command")

    # Start a new RayCluster with network limitation
    run_cmd('python3 setup.py --skip-config-ssh --shutdown')
    run_cmd(raycluster_cmd)

    time.sleep(5)

    # Delete the data in the cloud nodes
    run_cmd(f'ssh {cloud_node} rm -rf /home/ec2-user/share/Ray-Workloads/basics/image_tr/task_images')

    # Start the our scheduler
    run_cmd(f'ssh {head_node} python3 /home/ec2-user/ray/python/ray/scheduler/init.py', is_blocking=False)
    run_cmd(f"ssh {head_node} curl http://localhost:8000/get/node-info")

    # count the file number under task_images folder in head node
    run_cmd(f'ssh {head_node} ls /home/ec2-user/share/Ray-Workloads/basics/image_tr/task_images | wc -l', print_output=True)

    # Start the image.py
    start_time = time.time()
    if run_cmd(f'ssh {head_node} "cd /home/ec2-user/share/Ray-Workloads/basics/image_tr && python3 image.py sched"'):
        print("Command timeout")
        continue
    total_time = time.time() - start_time
    print(f"bandwidth: Total time with our scheduler: {total_time}")
    # count the file number under task_images folder in cloud node
    run_cmd(f'ssh {cloud_node} ls /home/ec2-user/share/Ray-Workloads/basics/image_tr/task_images | wc -l', print_output=True)
   
    run_cmd(f'ssh {cloud_node} rm -rf /home/ec2-user/share/Ray-Workloads/basics/image_tr/task_images')

    # break

    start_time = time.time()
    if run_cmd(f'ssh {head_node} "cd /home/ec2-user/share/Ray-Workloads/basics/image_tr && python3 image.py"'):
        print("Command timeout")
        continue
    total_time = time.time() - start_time
    print(f"bandwidth: Total time without our scheduler: {total_time}")
    # count the file number under task_images folder in cloud node
    run_cmd(f'ssh {cloud_node} ls /home/ec2-user/share/Ray-Workloads/basics/image_tr/task_images | wc -l', print_output=True)

    idx += 1
    print("===============================================")