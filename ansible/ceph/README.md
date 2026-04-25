ansible-playbook -i hosts.ini deploy.yml

sudo cephadm shell -- ceph orch host ls
sudo cephadm shell -- ceph -s
sudo cephadm shell -- ceph orch ps
sudo cephadm shell -- ceph orch device ls
sudo cephadm shell -- ceph orch ls # Проверьте статус развертывания



curl -X POST http://localhost:8000/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{
    "engine": "ceph",
    "job_type": "deploy",
    "hosts": [
      {
        "ip": "192.168.1.110",
        "ssh_user": "ubuntu",
        "ssh_port": 22,
        "ssh_private_key_path": "/home/ubuntu/.ssh/id_rsa"
      },
      {
        "ip": "192.168.1.112",
        "ssh_user": "ubuntu",
        "ssh_port": 22,
        "ssh_private_key_path": "/home/ubuntu/.ssh/id_rsa"
      },
      {
        "ip": "192.168.1.113",
        "ssh_user": "ubuntu",
        "ssh_port": 22,
        "ssh_private_key_path": "/home/ubuntu/.ssh/id_rsa"
      }
    ],
    "extra_vars": {
      "ceph_mon_host": "192.168.1.110",
      "ceph_osd_pool_default_size": 3,
      "ceph_osd_pool_default_min_size": 2,
      "ceph_network": "192.168.1.0/24",
      "ceph_cluster_network": "192.168.1.0/24",
      "ceph_rgw_enable": true
    }
  }'