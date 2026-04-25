import os

def generate_inventory_ceph(cluster_id: int, master_ip: str, nodes_ip: list, ssh_user: str, ssh_key_path: str):
    path = f"/tmp/cluster_{cluster_id}"
    os.makedirs(path, exist_ok=True)

    inventory_path = os.path.join(path, "hosts.ini")

    with open(inventory_path, "w") as f:
        f.write(f"[master]\n")
        f.write(f"node-master ansible_host={master_ip}\n")

        f.write(f"[workers]\n")
        for i, node in enumerate(nodes_ip):
            ip = node if isinstance(node, str) else node.ip
            f.write(f"node-0{i+1} ansible_host={ip}\n")
        
        f.write(f"[all:vars]\n")
        f.write(f"ansible_user={ssh_user}\n")
        f.write(f"ansible_ssh_private_key_file={ssh_key_path}\n")
        f.write(f"ansible_python_interpreter=/usr/bin/python3")

    return inventory_path