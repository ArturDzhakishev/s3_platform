# s3ctl

CLI-утилита для управления платформой развёртывания S3-совместимых хранилищ.  
Альтернатива веб-интерфейсу для работы из терминала и автоматизации.

## Сборка

```bash
go build -o s3ctl .

# Кросс-компиляция:
GOOS=linux   GOARCH=amd64 go build -o s3ctl-linux-amd64 .
GOOS=darwin  GOARCH=arm64 go build -o s3ctl-darwin-arm64 .
GOOS=windows GOARCH=amd64 go build -o s3ctl.exe .
```

## Конфигурация

Приоритет (от низшего к высшему):

1. `~/.s3ctl.yaml` — глобальный конфиг
2. `./.s3ctl.yaml` — локальный конфиг
3. Переменная окружения `S3CTL_API`
4. Флаг `--api`

```yaml
# ~/.s3ctl.yaml
api_url: http://192.168.1.124:8000
```

```bash
export S3CTL_API=http://192.168.1.124:8000
```

## Формат флага --node

```
--node "label,ip[,ssh_user[,ssh_port[,/path/to/key]]]"
```

Примеры:
```bash
--node "node1,192.168.1.110"                           # минимально
--node "node1,192.168.1.110,user,22"                   # с user и портом
--node "node1,192.168.1.110,user,22,~/.ssh/node1_key"  # со своим ключом
```

Глобальный `--key-file` применяется только к нодам, у которых ключ не задан.

## Использование

### Кластеры

```bash
# Список кластеров
s3ctl cluster list
s3ctl cluster list --engine seaweedfs
s3ctl cluster list --status ready

# Детали кластера
s3ctl cluster get <cluster-id>
```

#### Создание — Ceph

```bash
# Из файла
s3ctl cluster create --file examples/ceph.yaml --watch

# Из флагов — общий ключ для всех нод
./s3ctl cluster create \
  --name prod-ceph-01 \
  --engine ceph \
  --node "node-master,192.168.1.110,user,22,~/.ssh/ceph" \
  --node "node-02,192.168.1.112,user,22,~/.ssh/ceph" \
  --node "node-03,192.168.1.113,user,22,~/.ssh/ceph" \
  --extra "ceph_osd_pool_default_size=3" \
  --extra "ceph_osd_pool_default_min_size=2" \
  --extra "ceph_network=192.168.1.0/24" \
  --extra "ceph_rgw_enable=true" \
  --watch

# Из флагов — индивидуальный ключ для каждой ноды
s3ctl cluster create \
  --name prod-ceph-01 \
  --engine ceph \
  --node "node-master,192.168.1.110,user,22,~/.ssh/master_key" \
  --node "node-worker-1,192.168.1.112,user,22,~/.ssh/worker_key" \
  --node "node-worker-2,192.168.1.113,user,22,~/.ssh/worker_key" \
  --extra "ceph_osd_pool_default_size=3" \
  --extra "ceph_osd_pool_default_min_size=2" \
  --extra "ceph_network=192.168.1.0/24" \
  --extra "ceph_rgw_enable=true" \
  --watch
```

#### Создание — SeaweedFS

```bash
# Из файла
s3ctl cluster create --file examples/seaweedfs.yaml --watch

# Из флагов
s3ctl cluster create \
  --name prod-sw-01 \
  --engine seaweedfs \
  --node "node1,192.168.1.110,user,22" \
  --node "node2,192.168.1.112,user,22" \
  --node "node3,192.168.1.113,user,22" \
  --groups "seaweedfs,s3,loadbalancer" \
  --groups "seaweedfs,s3" \
  --groups "seaweedfs" \
  --key-file ~/.ssh/ceph \
  --extra "seaweedfs_version=3.63" \
  --extra "seaweedfs_s3_port=8333" \
  --extra "seaweedfs_volume_size_limit_mb=30000" \
  --watch
```

#### Создание — Garage

```bash
# Из файла
s3ctl cluster create --file examples/garage.yaml --watch

# Из флагов (--zone и --capacity применяются ко всем нодам)
s3ctl cluster create \
  --name prod-garage-01 \
  --engine garage \
  --node "node1,192.168.1.110,user,22" \
  --node "node2,192.168.1.112,user,22" \
  --node "node3,192.168.1.113,user,22" \
  --zone zone1 \
  --capacity 2G \
  --key-file ~/.ssh/ceph \
  --extra "garage_replication_factor=1" \
  --watch
```

#### Масштабирование

```bash
# Из файла
s3ctl cluster scale <cluster-id> --file examples/scale.yaml --watch

# Ceph
s3ctl cluster scale <cluster-id> \
  --node "node-worker-3,192.168.1.114,user,22" \
  --key-file ~/.ssh/ceph \
  --watch

# SeaweedFS
s3ctl cluster scale <cluster-id> \
  --node "node4,192.168.1.111,user,22" \
  --groups "seaweedfs,s3" \
  --key-file ~/.ssh/ceph \
  --watch

# Garage
s3ctl cluster scale <cluster-id> \
  --node "node4,192.168.1.111,user,22" \
  --zone zone1 \
  --capacity 2G \
  --key-file ~/.ssh/ceph \
  --watch
```

#### Удаление

```bash
# С подтверждением
s3ctl cluster delete <cluster-id>

# Без подтверждения + следить за teardown
s3ctl cluster delete <cluster-id> --yes --watch
```

### Задачи

```bash
s3ctl job list
s3ctl job list --status failed
s3ctl job list --limit 50

s3ctl job get   <job-id>
s3ctl job log   <job-id>         # с цветовой подсветкой Ansible
s3ctl job log   <job-id> --raw   # без подсветки
s3ctl job watch <job-id>         # polling каждые 3 сек до завершения
```

### Хосты

```bash
s3ctl host list
s3ctl host list --status available

s3ctl host ping --ip 192.168.1.110 --key-file ~/.ssh/id_rsa
s3ctl host ping --ip 192.168.1.110 --ssh-user ubuntu --key-file ~/.ssh/id_rsa
```

### Прочее

```bash
s3ctl playbooks             # список доступных плейбуков
s3ctl --json cluster list   # вывод в JSON для скриптов
s3ctl version               # версия утилиты
```

## Файлы конфигурации кластера

### SeaweedFS (`examples/seaweedfs.yaml`)

```yaml
name:   prod-seaweedfs-01
engine: seaweedfs
hosts:
  - label:               node1
    ip:                  192.168.1.110
    ssh_user:            user
    ssh_port:            22
    ssh_private_key_file: ~/.ssh/ceph
    groups:              [seaweedfs, s3, loadbalancer]
  - label:               node2
    ip:                  192.168.1.112
    ssh_user:            user
    ssh_port:            22
    ssh_private_key_file: ~/.ssh/ceph
    groups:              [seaweedfs, s3]
  - label:               node3
    ip:                  192.168.1.113
    ssh_user:            user
    ssh_port:            22
    ssh_private_key_file: ~/.ssh/ceph
    groups:              [seaweedfs]
extra_vars:
  seaweedfs_version: "3.63"
  seaweedfs_master_port: 9333
  seaweedfs_volume_port: 8080
  seaweedfs_filer_port: 8888
  seaweedfs_s3_port: 8333
  seaweedfs_volume_size_limit_mb: 30000
```

### Ceph (`examples/ceph.yaml`)

```yaml
name:   prod-ceph-01
engine: ceph
hosts:
  - label:               node-master
    ip:                  192.168.1.110
    ssh_user:            user
    ssh_port:            22
    ssh_private_key_file: ~/.ssh/ceph
  - label:               node-worker-1
    ip:                  192.168.1.112
    ssh_user:            user
    ssh_port:            22
    ssh_private_key_file: ~/.ssh/ceph
  - label:               node-worker-2
    ip:                  192.168.1.113
    ssh_user:            user
    ssh_port:            22
    ssh_private_key_file: ~/.ssh/ceph
extra_vars:
  ceph_osd_pool_default_size: 3
  ceph_osd_pool_default_min_size: 2
  ceph_network: "192.168.1.0/24"
  ceph_cluster_network: "192.168.1.0/24"
  ceph_rgw_enable: true
```

### Garage (`examples/garage.yaml`)

```yaml
name:   prod-garage-01
engine: garage
hosts:
  - label:               node1
    ip:                  192.168.1.110
    ssh_user:            user
    ssh_port:            22
    ssh_private_key_file: ~/.ssh/ceph
    zone:                zone1
    capacity:            2G
  - label:               node2
    ip:                  192.168.1.112
    ssh_user:            user
    ssh_port:            22
    ssh_private_key_file: ~/.ssh/ceph
    zone:                zone1
    capacity:            2G
  - label:               node3
    ip:                  192.168.1.113
    ssh_user:            user
    ssh_port:            22
    ssh_private_key_file: ~/.ssh/ceph
    zone:                zone1
    capacity:            2G
extra_vars:
  garage_version: "2.2.0"
  garage_rpc_port: 3901
  garage_replication_factor: 1
  name_bucket: "test"
```

### Scale (`examples/scale.yaml`)

```yaml
new_hosts:
  - label:               node4
    ip:                  192.168.1.111
    ssh_user:            user
    ssh_port:            22
    ssh_private_key_file: ~/.ssh/ceph
    groups:              [seaweedfs, s3]   # для SeaweedFS
    # zone:     zone1                      # для Garage
    # capacity: 2G                         # для Garage
```

## Структура исходного кода

```
s3ctl/
├── main.go       — точка входа
├── cli.go        — диспетчер команд, загрузка конфига
├── client.go     — HTTP-клиент для API бэкенда
├── types.go      — типы запросов/ответов, загрузка файлов
├── yaml.go       — YAML-парсер (без внешних зависимостей)
├── flags.go      — вспомогательные функции разбора флагов
├── cluster.go    — команды cluster *
├── job_host.go   — команды job *, host *, playbooks
├── format.go     — цветной вывод в терминал
└── examples/
    ├── seaweedfs.yaml
    ├── ceph.yaml
    ├── garage.yaml
    ├── scale.yaml
    └── .s3ctl.yaml
```

## Зависимости

Только стандартная библиотека Go — никаких внешних зависимостей.  
Бинарник полностью самодостаточен.
