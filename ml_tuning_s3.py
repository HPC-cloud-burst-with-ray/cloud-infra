import subprocess
import time
import os
import sys

head_node = "3.128.201.62"
cloud_node = "3.12.146.140"
timeout_duration = 60 * 15


def run_cmd(cmd, is_blocking=True, print_output=False):
    if not is_blocking:
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(10)
    else:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(cmd, result.stdout, result.stderr, result.returncode)
            exit(1)
        if print_output:
            print(result.stdout, result.stderr) 

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
    # Delete the data in the cloud nodes
    run_cmd(f'ssh {cloud_node} rm -rf /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch_s3')
    run_cmd(f'ssh {head_node} rm -rf /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch_s3')
    time.sleep(5)

    run_cmd(f'ssh {head_node} python /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/write_para.py '+bandwidth)

    # Start the our scheduler
    run_cmd(f'ssh {head_node} python3 /home/ec2-user/ray/python/ray/scheduler/init.py', is_blocking=False)
    run_cmd(f"ssh {head_node} curl http://localhost:8000/get/node-info")


    # Sched
    start_time = time.time()
    run_cmd(f'ssh {head_node} "cd /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/ && python3 param-server-s3.py sched cloud-bursting dataset_batch"')
    total_time = time.time() - start_time
    print(f"bandwidth: Total time with our scheduler: {total_time}")
    # count the file number under task_images folder in cloud node
    print("cloud:")
    run_cmd(f'ssh {cloud_node} ls /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch_s3 | wc -l', print_output=True)
    run_cmd(f'ssh {cloud_node} du -sh /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch_s3 ', print_output=True)

    print("hpc:")
    run_cmd(f'ssh {head_node} ls /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch_s3 | wc -l', print_output=True)
    run_cmd(f'ssh {head_node} du -sh /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch_s3', print_output=True)


    # Manu
    run_cmd(f'ssh {cloud_node} rm -rf /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch_s3')
    run_cmd(f'ssh {head_node} rm -rf /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch_s3')
    time.sleep(5)
    start_time = time.time()
    run_cmd(f'ssh {head_node} "cd /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/ && python3 param-server-s3.py manu cloud-bursting dataset_batch"')
    total_time = time.time() - start_time
    print(f"bandwidth: Total time without our scheduler: {total_time}")
    # count the file number under task_images folder in cloud node
    print("cloud:")
    run_cmd(f'ssh {cloud_node} ls /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch_s3 | wc -l', print_output=True)
    run_cmd(f'ssh {cloud_node} du -sh /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch_s3 ', print_output=True)
    print("hpc:")
    run_cmd(f'ssh {head_node} ls /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch_s3 | wc -l', print_output=True)
    run_cmd(f'ssh {head_node} du -sh /home/ec2-user/share/Ray-Workloads/ml/param-server-PASS/dataset_batch_s3', print_output=True)

    print("===============================================")