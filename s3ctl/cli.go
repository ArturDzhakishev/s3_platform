package main

import (
	"fmt"
	"os"
)

const usage = `s3ctl — CLI для управления платформой S3-хранилищ

Использование:
  s3ctl [глобальные флаги] <команда> [подкоманда] [флаги]

Глобальные флаги:
  --api   <url>   Адрес бэкенда (по умолч. http://localhost:8000)
                  Также: переменная окружения S3CTL_API или ~/.s3ctl.yaml
  --json          Вывод в формате JSON
  --no-color      Отключить цветной вывод

Команды:
  cluster list    [--engine ceph|seaweedfs|garage] [--status ...]
  cluster get     <id> [--show-secret]
  cluster create  --file <file.yaml>  |  --name .. --engine .. --node .. --key-file ..
  cluster delete  <id> [--yes] [--watch]
  cluster scale   <id> --file <file.yaml>  |  --node .. --key-file ..

  job list        [--status pending|running|success|failed] [--limit N]
  job get         <id>
  job log         <id> [--raw]
  job watch       <id>

  host list       [--status available|in_use|unreachable]
  host ping       --ip <ip> --key-file <path> [--ssh-user user] [--ssh-port 22]

Формат --node:
  label,ip[,ssh_user[,ssh_port]]
  Пример: --node "node1,192.168.1.110,user,22,~/.ssh/master_key"

Формат файла кластера (YAML или JSON):
  name:   prod-seaweedfs
  engine: seaweedfs
  hosts:
    - label: node1
      ip:    192.168.1.110
      ssh_user: user
      ssh_port: 22
      groups: [seaweedfs, s3, loadbalancer]
  extra_vars:
    seaweedfs_version: "3.63"

Примеры:
  s3ctl cluster list
  s3ctl cluster create --file cluster.yaml --watch
  s3ctl cluster create --name prod --engine ceph \
        --node "master,192.168.1.110" --node "w1,192.168.1.112" \
        --key-file ~/.ssh/id_rsa --watch
  s3ctl cluster scale <id> --node "node4,192.168.1.113" --key-file ~/.ssh/id_rsa
  s3ctl job watch <job-id>
  s3ctl host ping --ip 192.168.1.110 --key-file ~/.ssh/id_rsa
`

func run(args []string) error {
	// Разобрать глобальные флаги
	cfg := loadConfig()
	rest, err := parseGlobalFlags(args, cfg)
	if err != nil {
		return err
	}

	if len(rest) == 0 {
		fmt.Print(usage)
		return nil
	}

	client := newClient(cfg.APIURL)

	switch rest[0] {
	case "cluster", "cl", "c":
		return clusterCommand(client, cfg, rest[1:])
	case "job", "j":
		return jobCommand(client, cfg, rest[1:])
	case "host", "h":
		return hostCommand(client, cfg, rest[1:])
	case "playbooks":
		return cmdPlaybooks(client, cfg)
	case "help", "--help", "-h":
		fmt.Print(usage)
		return nil
	case "version":
		fmt.Println("s3ctl v1.0.0")
		return nil
	default:
		return fmt.Errorf("неизвестная команда: %q\nИспользуйте s3ctl --help", rest[0])
	}
}

// Config хранит глобальные настройки
type Config struct {
	APIURL  string
	JSON    bool
	NoColor bool
}

func parseGlobalFlags(args []string, cfg *Config) ([]string, error) {
	rest := []string{}
	i := 0
	for i < len(args) {
		switch args[i] {
		case "--api":
			if i+1 >= len(args) {
				return nil, fmt.Errorf("--api требует значение")
			}
			i++
			cfg.APIURL = args[i]
		case "--json":
			cfg.JSON = true
		case "--no-color":
			cfg.NoColor = true
		default:
			rest = append(rest, args[i])
		}
		i++
	}
	return rest, nil
}

func loadConfig() *Config {
	cfg := &Config{
		APIURL: "http://localhost:8000",
	}

	// 1. Прочитать ~/.s3ctl.yaml
	home, err := os.UserHomeDir()
	if err == nil {
		if data, err := os.ReadFile(home + "/.s3ctl.yaml"); err == nil {
			if v := yamlGetString(data, "api_url"); v != "" {
				cfg.APIURL = v
			}
		}
	}
	// Также .s3ctl.yaml в текущей директории
	if data, err := os.ReadFile(".s3ctl.yaml"); err == nil {
		if v := yamlGetString(data, "api_url"); v != "" {
			cfg.APIURL = v
		}
	}

	// 2. Переменная окружения перекрывает файл
	if v := os.Getenv("S3CTL_API"); v != "" {
		cfg.APIURL = v
	}
	return cfg
}
