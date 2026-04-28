```
curl -X POST http://localhost:8000/ceph/deploy -H "Content-Type: application/json" -d '{"type": "ceph", "master_ip": "192.168.1.110", "nodes_ip":["192.168.1.112","192.168.1.113"]}'
```

uvicorn app.main:app --reload


curl -s -X POST http://localhost:8000/api/v1/clusters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "prod-ceph-01",
    "engine": "ceph",
    "hosts": [
      {"label":"node-master","ip":"192.168.1.110",
       "ssh_user":"user","ssh_port":22,
       "ssh_private_key_path":"/home/user/.ssh/ceph"},
      {"label":"node-02","ip":"192.168.1.112",
       "ssh_user":"user","ssh_port":22,
       "ssh_private_key_path":"/home/user/.ssh/ceph"},
      {"label":"node-03","ip":"192.168.1.113",
       "ssh_user":"user","ssh_port":22,
       "ssh_private_key_path":"/home/user/.ssh/ceph"}
    ],
    "extra_vars": {
      "ceph_mon_host": "192.168.1.110",
      "ceph_osd_pool_default_size": 3,
      "ceph_osd_pool_default_min_size": 2,
      "ceph_network": "192.168.1.0/24",
      "ceph_cluster_network": "192.168.1.0/24",
      "ceph_rgw_enable": true
    }
  }' | jq .

  <!-- Seaweedfs deploy -->

curl -s -X POST http://localhost:8000/api/v1/clusters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "prod-ceph-01",
    "engine": "seaweedfs",
    "hosts": [
      {"label":"node-master","ip":"192.168.1.110",
        "ssh_user":"user","ssh_port":22,
        "ssh_private_key_path":"/home/user/.ssh/ceph"},
      {"label":"node-02","ip":"192.168.1.112",
        "ssh_user":"user","ssh_port":22,
        "ssh_private_key_path":"/home/user/.ssh/ceph"},
      {"label":"node-03","ip":"192.168.1.113",
        "ssh_user":"user","ssh_port":22,
        "ssh_private_key_path":"/home/user/.ssh/ceph"}
    ]
  }' | jq .