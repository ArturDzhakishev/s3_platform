```
curl -X POST http://localhost:8000/ceph/deploy -H "Content-Type: application/json" -d '{"type": "ceph", "master_ip": "192.168.1.110", "nodes_ip":["192.168.1.112","192.168.1.113"]}'
```

uvicorn app.main:app --reload


curl -X POST http://localhost:8000/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{
    "engine": "ceph",
    "job_type": "deploy",
    "hosts": [
      {
        "ip": "192.168.1.110",
        "ssh_user": "user",
        "ssh_port": 22,
        "ssh_private_key_path": "/home/user/.ssh/ceph"
      },
      {
        "ip": "192.168.1.112",
        "ssh_user": "user",
        "ssh_port": 22,
        "ssh_private_key_path": "/home/user/.ssh/ceph"
      },
      {
        "ip": "192.168.1.113",
        "ssh_user": "user",
        "ssh_port": 22,
        "ssh_private_key_path": "/home/user/.ssh/ceph"
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


Ceph_cluster

curl -X POST http://localhost:8000/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{
    "engine":   "ceph",
    "job_type": "deploy",
    "extra_vars": {
      "ceph_osd_pool_default_size": 3
    }
  }'


curl -X POST http://localhost:8000/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{
    "engine":   "seaweedfs",
    "job_type": "deploy",
    "extra_vars": {
      "ceph_osd_pool_default_size": 3
    }
  }'

curl -X POST http://localhost:8000/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{
    "engine":   "garage",
    "job_type": "deploy",
    "extra_vars": {
      "ceph_osd_pool_default_size": 3
    }
  }'

Ping
curl -X POST http://localhost:8000/api/v1/ping \
-H "Content-Type: application/json" \
-d '{
"host": {
    "ip":                   "192.168.1.110",
    "ssh_user":             "user",
    "ssh_port":             22,
    "ssh_private_key_path": "/home/user/.ssh/ceph"
}
}'