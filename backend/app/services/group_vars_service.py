import os
import yaml

def generate_group_vars(cluster_id: int, data: dict):
    base_path = f"/tmp/cluster_{cluster_id}"
    group_vars_path = os.path.join(base_path, "group_vars")

    os.makedirs(group_vars_path, exist_ok=True)

    # общий конфиг
    with open(os.path.join(group_vars_path, "all.yml"), "w") as f:
        yaml.dump(data.get("all", {}), f)

    # конфиг под конкретное хранилище
    if "storage_type" in data:
        filename = f"{data['storage_type']}.yml"
        with open(os.path.join(group_vars_path, filename), "w") as f:
            yaml.dump(data.get("storage_config", {}), f)

    return group_vars_path