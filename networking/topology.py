import json
import networkx as nx

class NetworkCondition:
    def __init__(self, rtt=(0, 0), bandwidth=(0, 0), jitter=(0, 0), loss=(0, 0)):
        # check if all the tuples are of length 2
        if len(rtt) != 2 or len(bandwidth) != 2 or len(jitter) != 2 or len(loss) != 2:
            print("Invalid network condition values, follow format (mean, std).")
            return
        self.rtt = rtt
        self.bandwidth = bandwidth
        self.jitter = jitter
        self.loss = loss

    def set_rtt(self, mean, std_dev):
        self.rtt = (mean, std_dev)
    
    def set_bandwidth(self, mean, std_dev):
        self.bandwidth = (mean, std_dev)
    
    def set_jitter(self, mean, std_dev):
        self.jitter = (mean, std_dev)

    def set_loss(self, mean, std_dev):
        self.loss = (mean, std_dev)

    def __repr__(self):
        return f"NetworkCondition(rtt={self.rtt}, bandwidth={self.bandwidth}, jitter={self.jitter}, loss={self.loss})"
    
    def to_dict(self):
        return {
            "rtt": self.rtt,
            "bandwidth": self.bandwidth,
            "jitter": self.jitter,
            "loss": self.loss
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


def encode_network_condition(obj):
    if isinstance(obj, NetworkCondition):
        return obj.to_dict()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def decode_network_condition(dct):
    if all(key in dct for key in ("rtt", "bandwidth", "jitter", "loss")):
        return NetworkCondition.from_dict(dct)
    return dct


class NetworkTopology:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.graph.add_node("Cloud")
        self.graph.add_node("HPCLogin")
        self.graph.add_node("HPCWorker")

    def add_edge(self, node1, node2, condition: NetworkCondition):
        if node1 not in self.graph.nodes or node2 not in self.graph.nodes:
            print(f"Node {node1} or {node2} not found in the network topology.")
            return
        self.graph.add_edge(node1, node2, condition=condition)

    def describe_edge(self, edge):
        condition = self.graph.edges[edge]["condition"]
        print(f"Edge {edge} has condition: bandwidth={condition.bandwidth}")

    def set_edge_condition(self, edge, condition: NetworkCondition):
        if edge in self.graph.edges:
            self.graph.edges[edge]["condition"] = condition
        else:
            print(f"Edge {edge} not found in the network topology.")

    def export_to_json(self, json_path="network_topology.json"):
        # export the network topology to a json file
        data = nx.node_link_data(self.graph)
        with open(json_path, "w") as file:
            json.dump(data, file, indent=4, default=encode_network_condition)

    def import_from_json(self, json_path):
        # import the network topology from a json file
        with open(json_path, "r") as file:
            data = json.load(file, object_hook=decode_network_condition)
            self.graph = nx.node_link_graph(data)


# if __name__ == "__main__":
#     network_condition = NetworkCondition()
#     network_condition.set_rtt(100, 10)
#     network_condition.set_bandwidth(100, 10)
#     network_condition.set_jitter(100, 10)
#     network_condition.set_loss(100, 10)
#     print(json.dumps(network_condition.get_json(), indent=4))