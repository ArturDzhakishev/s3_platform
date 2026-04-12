ansible-playbook -i hosts.ini deploy.yml

sudo cephadm shell -- ceph orch host ls
sudo cephadm shell -- ceph -s
sudo cephadm shell -- ceph orch ps
sudo cephadm shell -- ceph orch device ls
sudo cephadm shell -- ceph orch ls # Проверьте статус развертывания