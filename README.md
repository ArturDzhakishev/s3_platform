```
curl -X POST http://localhost:8000/ceph/deploy -H "Content-Type: application/json" -d '{"type": "ceph", "master_ip": "192.168.1.110", "nodes_ip":["192.168.1.112","192.168.1.113"]}'
```