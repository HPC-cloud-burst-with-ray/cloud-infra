from topology import NetworkTopology
from topology import NetworkCondition

'''
tc commands to set delay, bandwidth, jitter, and and packet loss (even = 0) to a certain network interface and a specific IP

sudo iptables -t mangle -A OUTPUT -p tcp -d 192.168.1.100 -j MARK --set-mark 1

sudo tc qdisc add dev eth0 root handle 1: prio

sudo tc qdisc add dev eth0 parent 1:3 handle 30: netem delay 20ms 2ms
sudo tc qdisc add dev eth0 parent 30:1 handle 31: tbf rate 6mbit burst 32kbit latency 50ms

sudo tc filter add dev eth0 protocol ip parent 1:0 prio 3 handle 1 fw flowid 1:3
'''
    
# let NetworkEmulator a derived class of NetworkTopology
class NetworkEmulator(NetworkTopology):
    def __init__(self, topology_file = None):
        super().__init__()
        # if there is a topology file, load it into the NetworkTopolog
        if topology_file:
            self.import_from_json(topology_file)

    def __get_netem_filter_commands(self, edge, device, target_ip):
        pass

    def __get_netem_qdisc_commands(self, edge, device):
        pass

    def __get_edge_condition(self, edge):
        return self.graph.edges[edge]["condition"]

    def get_netem_setup_commands(self, edge, device, target_ip):
        network_condition = self.__get_edge_condition(edge)
        # print(network_condition.to_dict())

    def get_netem_disable_commands(self, edge, device):
        pass

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

    # read topology file and test command generation
    netem = NetworkEmulator("network_topology_no_sshuttle.json")
    netem.describe_edge(("Cloud", "HPCWorker"))
    # test generate tc netem commands
    print("[NOTE] tc affects the outgoing traffic, so the commands are generated for the source node")
    print("HPCLogin -> Cloud, apply command to HPCLogin")
    netem.get_netem_setup_commands(("HPCLogin", "Cloud"), "ens5", "54.211.29.176")