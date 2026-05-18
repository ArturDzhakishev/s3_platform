# s3ctl

CLI-утилита для управления платформой развёртывания S3-совместимых хранилищ.  
Альтернатива веб-интерфейсу для работы из терминала и автоматизации.

## Сборка

```bash
go build -o s3ctl .

# Для другой платформы (кросс-компиляция):
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

## Использование

### Кластеры

```bash
# Список кластеров
s3ctl cluster list
s3ctl cluster list --engine seaweedfs
s3ctl cluster list --status ready

# Детали кластера
s3ctl cluster get <cluster-id>
s3ctl cluster get <cluster-id> --show-secret   # показать secret_key полностью

# Создать из файла
s3ctl cluster create --file examples/seaweedfs.yaml
s3ctl cluster create --file examples/seaweedfs.yaml --watch   # ждать завершения

# Создать из флагов
# Ceph
s3ctl cluster create \
  --name prod-ceph-01 \
  --engine ceph \
  --node "node-master,192.168.1.110,user,22" \
  --node "node-worker-1,192.168.1.112,user,22" \
  --node "node-worker-2,192.168.1.113,user,22" \
  --key-file ~/.ssh/ceph \
  --extra "ceph_osd_pool_default_size=3" \
  --extra "ceph_osd_pool_default_min_size=2" \
  --extra "ceph_network=192.168.1.0/24" \
  --extra "ceph_rgw_enable=true" \
  --watch

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
  --watch

# Garage (с zone и capacity)
s3ctl cluster create \
  --name prod-garage \
  --engine garage \
  --node "node1,192.168.1.110" \
  --node "node2,192.168.1.112" \
  --zone zone1 --capacity 2G \
  --key-file ~/.ssh/id_rsa

# Масштабирование
s3ctl cluster scale <id> --file examples/scale.yaml --watch
# Ceph
s3ctl cluster scale <id> \
  --node "node-01,192.168.1.111" \
  --key-file ~/.ssh/ceph \
  --watch

s3ctl cluster scale <id> \
  --node "node4,192.168.1.111" \
  --groups "seaweedfs,s3" \
  --key-file ~/.ssh/id_rsa \
  --watch

# Удалить кластер
s3ctl cluster delete <id>
s3ctl cluster delete <id> --yes --watch    # без подтверждения
```

### Задачи

```bash
s3ctl job list
s3ctl job list --status failed
s3ctl job list --limit 50

s3ctl job get  <job-id>
s3ctl job log  <job-id>        # с цветовой подсветкой Ansible
s3ctl job log  <job-id> --raw  # без подсветки
s3ctl job watch <job-id>       # polling каждые 3 сек до завершения
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
s3ctl playbooks            # список доступных плейбуков
s3ctl --json cluster list  # вывод в JSON для скриптов
```

## Файлы конфигурации кластера

### SeaweedFS (`examples/seaweedfs.yaml`)

```yaml
name:   prod-seaweedfs-01
engine: seaweedfs
hosts:
  - label: node1
    ip:    192.168.1.110
    ssh_user: user
    groups: [seaweedfs, s3, loadbalancer]
  - label: node2
    ip:    192.168.1.112
    groups: [seaweedfs, s3]
extra_vars:
  seaweedfs_version: "3.63"
  seaweedfs_s3_port: 8333
```

### Garage (`examples/garage.yaml`)

```yaml
name:   prod-garage-01
engine: garage
hosts:
  - label: node1
    ip:    192.168.1.110
    zone:  zone1
    capacity: 2G
extra_vars:
  garage_replication_factor: 1
```

### Scale (`examples/scale.yaml`)

```yaml
new_hosts:
  - label: node4
    ip:    192.168.1.111
    groups: [seaweedfs, s3]
```

## Структура исходного кода

```
s3ctl/
├── main.go       — точка входа
├── cli.go        — диспетчер команд, загрузка конфига
├── client.go     — HTTP-клиент для API бэкенда
├── types.go      — типы запросов/ответов, загрузка файлов
├── yaml.go       — минималистичный YAML-парсер
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
