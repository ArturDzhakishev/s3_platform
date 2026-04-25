from app.services.ansible_service import run_ansible
from app.services.inventory_service import generate_inventory_ceph
from app.services.group_vars_service import generate_group_vars


# -------- CEPH --------
def deploy_ceph_task(cluster_id, data):
    # для ceph можно сделать 2 группы
    inventory = generate_inventory_ceph(
        cluster_id,
        data.master_ip,
        data.nodes_ip,
        data.ssh_user,
        data.ssh_key_path
    )

    group_vars = 

    run_ansible(
        data.type,
        inventory
    )

    print(f"[SUCCESS] Cluster {cluster_id} deployed")