import subprocess

def run_ansible(storage, inventory_path):
    try:
        result = subprocess.run([
        "ansible-playbook",
        "-i", inventory_path,
        "deploy.yml"
    ],
    cwd=f"ansible/{storage}",
    capture_output=True, 
    text=True, 
    check=True)
    except subprocess.CalledProcessError as e:
        # Выведите это в терминал, где запущен uvicorn
        print("--- FULL ANSIBLE OUTPUT ---")
        print(e.stdout) 
        print(e.stderr)
        raise

    return result.stdout