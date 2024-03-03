# from .topology import NetworkTopology
# from .topology import NetworkCondition

# run the file as a script for unit testing, or part of the package
try :
    from .topology import NetworkTopology
    from .topology import NetworkCondition
    from .topology import CLOUD, HPC_LOGIN, HPC_WORKER
except ImportError:
    from topology import NetworkTopology
    from topology import NetworkCondition
    from topology import CLOUD, HPC_LOGIN, HPC_WORKER

'''
template commands below

tc commands to set delay, bandwidth, jitter, and and packet loss (even = 0) to a certain network interface and a specific IP

sudo iptables -t mangle -A OUTPUT -p tcp -d 192.168.1.100 -j MARK --set-mark 1

sudo tc qdisc add dev eth0 root handle 1: prio

sudo tc qdisc add dev eth0 parent 1:3 handle 30: netem delay 20ms 2ms
sudo tc qdisc add dev eth0 parent 30:1 handle 31: tbf rate 6mbit burst 32kbit latency 20ms

sudo tc filter add dev eth0 protocol ip parent 1:0 prio 3 handle 1 fw flowid 1:3
'''
    
# let NetworkEmulator a derived class of NetworkTopology
class NetworkEmulator(NetworkTopology):
    def __init__(self, topology_file = None):
        super().__init__()
        # if there is a topology file, load it into the NetworkTopolog
        if topology_file:
            self.import_from_json(topology_file)

    def __get_edge_condition(self, edge):
        return self.graph.edges[edge]["condition"]

    def get_netem_setup_commands(self, edge, device, target_ip, link_id=1):
        mask = link_id
        qdisc_handle = link_id
        netem_handle = qdisc_handle * 10 + 0
        tbf_handle = qdisc_handle * 10 + 1
        network_condition = self.__get_edge_condition(edge)
        bandwidth = network_condition.bandwidth
        rtt = network_condition.rtt
        commands = [
            # f"sudo iptables -t mangle -A OUTPUT -p tcp -d {target_ip} -j MARK --set-mark 1",
            f"sudo iptables -t mangle -A OUTPUT -d {target_ip} -j MARK --set-mark {mask}",
            # f"sudo iptables -t mangle -A OUTPUT -p tcp -d {target_ip} --tcp-flags ALL ACK -j RETURN",
            f"sudo tc qdisc add dev {device} root handle {qdisc_handle}: prio",
            f"sudo tc qdisc add dev {device} parent {qdisc_handle}:3 handle {netem_handle}: netem delay {rtt[0]/2}ms {rtt[1]/2}ms",
            f"sudo tc qdisc add dev {device} parent {netem_handle}:1 handle {tbf_handle}: tbf rate {bandwidth[0]}mbit burst 256kbit latency 30ms",
            f"sudo tc filter add dev {device} protocol ip parent {qdisc_handle}:0 prio 3 handle {mask} fw flowid {qdisc_handle}:3"
        ]
        return commands


    def get_netem_disable_commands(self, device, target_ip=None, link_id=1):
        mask = link_id
        if target_ip is None:
            commands = [
                f"sudo tc qdisc del dev {device} root",
                f"sudo iptables -t mangle -F OUTPUT",
            ]
        else:
            commands = [
                f"sudo tc qdisc del dev {device} root",
                # f"sudo iptables -t mangle -D OUTPUT -p tcp -d {target_ip} -j MARK --set-mark 1",
                f"sudo iptables -t mangle -D OUTPUT -d {target_ip} -j MARK --set-mark {mask}",
            ]
        return commands
    
    def get_netem_qdisc_status_commands(self, device):
        commands = [
            f"sudo tc qdisc show dev {device}"
        ]
        return commands
    
    def get_iptables_mangle_status_commands(self):
        # sudo iptables -t mangle -L OUTPUT -v -n
        commands = [
            f"sudo iptables -t mangle -L OUTPUT -v -n"
        ]
        return commands

if __name__ == "__main__":
    netem = NetworkEmulator()
    netem.add_edge("HPCLogin", "HPCWorker", NetworkCondition(rtt=(1, 0), bandwidth=(900, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "HPCLogin", NetworkCondition(rtt=(1, 0), bandwidth=(900, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "HPCWorker", NetworkCondition(rtt=(1, 0), bandwidth=(900, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "Cloud", NetworkCondition(rtt=(0.3, 0), bandwidth=(5000, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "HPCLogin", NetworkCondition(rtt=(20, 0), bandwidth=(1000, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "HPCWorker", NetworkCondition(rtt=(20, 0), bandwidth=(650, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCLogin", "Cloud", NetworkCondition(rtt=(20, 0), bandwidth=(6, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "Cloud", NetworkCondition(rtt=(20, 0), bandwidth=(6, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.export_to_json("network_topology_no_sshuttle.json")

    netem = NetworkEmulator()
    netem.add_edge("HPCLogin", "HPCWorker", NetworkCondition(rtt=(1, 0), bandwidth=(900, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "HPCLogin", NetworkCondition(rtt=(1, 0), bandwidth=(900, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "HPCWorker", NetworkCondition(rtt=(1, 0), bandwidth=(900, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "Cloud", NetworkCondition(rtt=(0.3, 0), bandwidth=(5000, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "HPCLogin", NetworkCondition(rtt=(20, 0), bandwidth=(12, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "HPCWorker", NetworkCondition(rtt=(20, 0), bandwidth=(12, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCLogin", "Cloud", NetworkCondition(rtt=(20, 0), bandwidth=(4, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "Cloud", NetworkCondition(rtt=(20, 0), bandwidth=(4, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.export_to_json("network_topology_sshuttle.json")

    netem = NetworkEmulator()
    netem.add_edge("HPCLogin", "HPCWorker", NetworkCondition(rtt=(1, 0), bandwidth=(900, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "HPCLogin", NetworkCondition(rtt=(1, 0), bandwidth=(900, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "HPCWorker", NetworkCondition(rtt=(1, 0), bandwidth=(900, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "Cloud", NetworkCondition(rtt=(0.3, 0), bandwidth=(5000, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "HPCLogin", NetworkCondition(rtt=(20, 0), bandwidth=(12, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "HPCWorker", NetworkCondition(rtt=(20, 0), bandwidth=(12, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCLogin", "Cloud", NetworkCondition(rtt=(20, 0), bandwidth=(6, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "Cloud", NetworkCondition(rtt=(20, 0), bandwidth=(6, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.export_to_json("network_topology_sshuttle_ray.json")

    netem = NetworkEmulator()
    netem.add_edge("HPCLogin", "HPCWorker", NetworkCondition(rtt=(0.3, 0), bandwidth=(900, 0), jitter=(0.01, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "HPCLogin", NetworkCondition(rtt=(0.3, 0), bandwidth=(900, 0), jitter=(0.01, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "HPCWorker", NetworkCondition(rtt=(0.3, 0), bandwidth=(900, 0), jitter=(0.01, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "Cloud", NetworkCondition(rtt=(0.3, 0), bandwidth=(5000, 0), jitter=(0.01, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "HPCLogin", NetworkCondition(rtt=(0.3, 0), bandwidth=(106, 0), jitter=(0.01, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "HPCWorker", NetworkCondition(rtt=(0.3, 0), bandwidth=(106, 0), jitter=(0.01, 0), loss=(0, 0)))
    netem.add_edge("HPCLogin", "Cloud", NetworkCondition(rtt=(0.3, 0), bandwidth=(106, 0), jitter=(0.01, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "Cloud", NetworkCondition(rtt=(0.3, 0), bandwidth=(106, 0), jitter=(0.01, 0), loss=(0, 0)))
    netem.export_to_json("network_topology_test_case.json")

    # read topology file and test command generation
    netem = NetworkEmulator("network_topology_no_sshuttle.json")
    netem.describe_edge(("Cloud", "HPCWorker"))
    # test generate tc netem commands
    print("[NOTE] tc affects the outgoing traffic, so the commands are generated for the source node")
    print("HPCLogin -> Cloud, apply command to HPCLogin")
    # hpc_pri_ip = "10.0.0.13"
    hpc_pub_ip = "54.226.111.220"
    cloud_pub_ip = "54.211.29.176"
    device = "ens5"
    print("commands for HPCLogin -> Cloud")
    login_node_commands = netem.get_netem_setup_commands(("HPCLogin", "Cloud"), device, cloud_pub_ip)
    for command in login_node_commands:
        print(command)
    print()
    print("commands for Cloud -> HPCLogin")
    # cloud_node_commands = netem.get_netem_setup_commands(("Cloud", "HPCLogin"), device, hpc_pri_ip)
    cloud_node_commands = netem.get_netem_setup_commands(("Cloud", "HPCLogin"), device, hpc_pub_ip)
    for command in cloud_node_commands:
        print(command)
    print()
    print("commands for disable network emulation HPCLogin -> Cloud")
    login_node_disable_commands = netem.get_netem_disable_commands(device, cloud_pub_ip)
    for command in login_node_disable_commands:
        print(command)
    print()
    print("commands for disable network emulation Cloud -> HPCLogin")
    # cloud_node_disable_commands = netem.get_netem_disable_commands(device, hpc_pri_ip)
    cloud_node_disable_commands = netem.get_netem_disable_commands(device, hpc_pub_ip)
    for command in cloud_node_disable_commands:
        print(command)
    print()

