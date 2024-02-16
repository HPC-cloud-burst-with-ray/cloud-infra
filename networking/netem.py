from topology import NetworkTopology
from topology import NetworkCondition
    
# let NetworkEmulator a derived class of NetworkTopology
class NetworkEmulator(NetworkTopology):
    def __init__(self, topology_file = None):
        super().__init__()
        # if there is a topology file, load it into the NetworkTopolog
        if topology_file:
            self.import_from_json(topology_file)

    def get_netem_command(self, edge):
        pass

if __name__ == "__main__":
    netem = NetworkEmulator()
    netem.add_edge("HPCLogin", "HPCWorker", NetworkCondition(rtt=(10, 0), bandwidth=(900, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "HPCLogin", NetworkCondition(rtt=(10, 0), bandwidth=(900, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "HPCWorker", NetworkCondition(rtt=(10, 0), bandwidth=(900, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "Cloud", NetworkCondition(rtt=(10, 0), bandwidth=(5000, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "HPCLogin", NetworkCondition(rtt=(10, 0), bandwidth=(6, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("Cloud", "HPCWorker", NetworkCondition(rtt=(10, 0), bandwidth=(650, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCLogin", "Cloud", NetworkCondition(rtt=(10, 0), bandwidth=(1000, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.add_edge("HPCWorker", "Cloud", NetworkCondition(rtt=(10, 0), bandwidth=(6, 0), jitter=(0.1, 0), loss=(0, 0)))
    netem.export_to_json()
    netem.describe_edge(("HPCLogin", "HPCWorker"))
    del netem
    netem = NetworkEmulator("network_topology.json")
    netem.describe_edge(("Cloud", "HPCWorker"))