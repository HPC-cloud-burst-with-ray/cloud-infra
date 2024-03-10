import paramiko


# check_conda_python310_commands = ["conda --version &> /dev/null && conda env list | grep -q 'myenv' || echo 'FAILED to find conda myenv' "]

config_conda_commands = ["cd ~ && [ ! -d 'setup_bashrc' ] && git clone https://github.com/HPC-cloud-burst-with-ray/setup_bashrc.git",
                            "cd ~/setup_bashrc && cat add_to_bashrc.txt >> ~/.bashrc",]


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


if __name__ == "__main__":
    # run commands on remote node
    node_ip = "18.215.159.135"
    user_name = "ec2-user"
    worker_ip = "10.0.1.214"
    worker_user_name = "ec2-user"
    commands = config_conda_commands
    # run_commands_ssh(node_ip, user_name, commands)
    run_commands_ssh_via_login(node_ip, user_name, worker_ip, worker_user_name, commands)

