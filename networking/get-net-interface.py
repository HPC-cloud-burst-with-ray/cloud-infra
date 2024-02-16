import psutil
import socket

# Get the list of all network interfaces
network_interfaces = psutil.net_if_addrs()

hostname = socket.gethostname()
ip_addr = socket.gethostbyname(hostname)

# Print the names of the network interfaces
for k, v in network_interfaces.items():
    if v[0].address == ip_addr:
        print(f"{k}")
        break

