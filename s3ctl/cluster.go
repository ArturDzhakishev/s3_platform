package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"
)

func clusterCommand(cl *Client, cfg *Config, args []string) error {
	if len(args) == 0 {
		fmt.Println("Подкоманды: list, get, create, delete, scale")
		return nil
	}
	switch args[0] {
	case "list", "ls":
		return cmdClusterList(cl, cfg, args[1:])
	case "get":
		return cmdClusterGet(cl, cfg, args[1:])
	case "create":
		return cmdClusterCreate(cl, cfg, args[1:])
	case "delete", "del", "rm":
		return cmdClusterDelete(cl, cfg, args[1:])
	case "scale":
		return cmdClusterScale(cl, cfg, args[1:])
	default:
		return fmt.Errorf("неизвестная подкоманда cluster %q", args[0])
	}
}

// ── cluster list ──────────────────────────────────────────────────────────────

func cmdClusterList(cl *Client, cfg *Config, args []string) error {
	engine := flagString(args, "--engine", "")
	status := flagString(args, "--status", "")

	path := "/clusters"
	var params []string
	if engine != "" {
		params = append(params, "engine="+engine)
	}
	if status != "" {
		params = append(params, "status="+status)
	}
	if len(params) > 0 {
		path += "?" + strings.Join(params, "&")
	}

	data, err := cl.GET(path)
	if err != nil {
		return err
	}
	if cfg.JSON {
		printJSONRaw(data)
		return nil
	}

	var clusters []ClusterResponse
	if err := json.Unmarshal(data, &clusters); err != nil {
		return err
	}
	if len(clusters) == 0 {
		fmt.Println("Кластеров нет.")
		return nil
	}
	hdr(fmt.Sprintf("Кластеры (%d)", len(clusters)))
	for _, c := range clusters {
		printCluster(c)
		sep()
	}
	return nil
}

// ── cluster get ───────────────────────────────────────────────────────────────

func cmdClusterGet(cl *Client, cfg *Config, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("cluster get <cluster-id>")
	}
	data, err := cl.GET("/clusters/" + args[0])
	if err != nil {
		return err
	}
	if cfg.JSON {
		printJSONRaw(data)
		return nil
	}
	var cluster ClusterResponse
	if err := json.Unmarshal(data, &cluster); err != nil {
		return err
	}
	hdr("Кластер")
	printCluster(cluster)
	return nil
}

// ── cluster create ────────────────────────────────────────────────────────────

func cmdClusterCreate(cl *Client, cfg *Config, args []string) error {
	file := flagString(args, "--file", flagString(args, "-f", ""))
	watch := flagBool(args, "--watch")

	var req *CreateClusterRequest

	if file != "" {
		var err error
		req, err = LoadClusterFile(file)
		if err != nil {
			return err
		}
	} else {
		req = &CreateClusterRequest{
			ExtraVars: make(map[string]interface{}),
		}
		req.Name = flagString(args, "--name", "")
		req.Engine = flagString(args, "--engine", "")
		sshUser := flagString(args, "--ssh-user", "user")

		// Собрать ноды из --node флагов
		nodeStrs := flagStringArray(args, "--node")
		groupStrs := flagStringArray(args, "--groups")
		zone := flagString(args, "--zone", "")
		capacity := flagString(args, "--capacity", "")

		for i, ns := range nodeStrs {
			h, err := parseNodeStr(ns)
			if err != nil {
				return err
			}
			if h.SSHUser == "" {
				h.SSHUser = sshUser
			}
			if zone != "" && h.Zone == "" {
				h.Zone = zone
			}
			if capacity != "" && h.Capacity == "" {
				h.Capacity = capacity
			}
			if i < len(groupStrs) {
				h.Groups = strings.Split(groupStrs[i], ",")
			}
			req.Hosts = append(req.Hosts, *h)
		}

		// extra_vars из --extra key=value
		for _, kv := range flagStringArray(args, "--extra") {
			parts := strings.SplitN(kv, "=", 2)
			if len(parts) == 2 {
				req.ExtraVars[parts[0]] = parts[1]
			}
		}
	}

	// Применить SSH ключ из файла ко всем нодам
	keyFile := flagString(args, "--key-file", "")
	if keyFile != "" {
		pem, err := os.ReadFile(keyFile)
		if err != nil {
			return fmt.Errorf("не удалось прочитать ключ %s: %w", keyFile, err)
		}
		for i := range req.Hosts {
			if req.Hosts[i].SSHPrivateKey == "" {
				req.Hosts[i].SSHPrivateKey = string(pem)
			}
		}
	}

	// Валидация и дефолты
	if req.Name == "" {
		return fmt.Errorf("--name обязателен")
	}
	if req.Engine == "" {
		return fmt.Errorf("--engine обязателен (ceph, seaweedfs, garage)")
	}
	if len(req.Hosts) == 0 {
		return fmt.Errorf("нужна хотя бы одна нода (--node или --file)")
	}
	for i := range req.Hosts {
		if req.Hosts[i].SSHPort == 0 {
			req.Hosts[i].SSHPort = 22
		}
		if req.Hosts[i].SSHUser == "" {
			req.Hosts[i].SSHUser = "user"
		}
		if i == 0 {
			req.Hosts[i].Role = "master"
		} else if req.Hosts[i].Role == "" {
			req.Hosts[i].Role = "worker"
		}
	}

	data, err := cl.POST("/clusters", req)
	if err != nil {
		return err
	}
	if cfg.JSON {
		printJSONRaw(data)
		return nil
	}

	var resp AcceptedResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return err
	}

	fmt.Printf("\n  %s Кластер создаётся\n", c(cGreen, "✓"))
	fmt.Printf("  cluster_id: %s\n", c(cBold, resp.ClusterID))
	fmt.Printf("  job_id:     %s\n", c(cCyan, resp.JobID))
	fmt.Printf("  playbook:   %s\n", resp.Playbook)

	if watch {
		return watchJob(cl, cfg, resp.JobID)
	}
	fmt.Printf("\n  Лог:    s3ctl job watch %s\n", resp.JobID)
	return nil
}

// ── cluster delete ────────────────────────────────────────────────────────────

func cmdClusterDelete(cl *Client, cfg *Config, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("cluster delete <cluster-id>")
	}
	id := args[0]
	yes := flagBool(args, "--yes")
	watch := flagBool(args, "--watch")

	if !yes {
		fmt.Printf("Удалить кластер %s? [y/N] ", id)
		var confirm string
		fmt.Scan(&confirm)
		if confirm != "y" && confirm != "Y" {
			fmt.Println("Отменено.")
			return nil
		}
	}

	data, err := cl.DELETE("/clusters/" + id)
	if err != nil {
		return err
	}
	if cfg.JSON {
		printJSONRaw(data)
		return nil
	}
	var resp AcceptedResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return err
	}
	fmt.Printf("  %s Teardown запущен  job_id: %s\n",
		c(cYellow, "→"), c(cCyan, resp.JobID))
	if watch {
		return watchJob(cl, cfg, resp.JobID)
	}
	return nil
}

// ── cluster scale ─────────────────────────────────────────────────────────────

func cmdClusterScale(cl *Client, cfg *Config, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("cluster scale <cluster-id> [опции]")
	}
	id := args[0]
	args = args[1:]
	file := flagString(args, "--file", flagString(args, "-f", ""))
	watch := flagBool(args, "--watch")

	var req *ScaleRequest

	if file != "" {
		var err error
		req, err = LoadScaleFile(file)
		if err != nil {
			return err
		}
	} else {
		req = &ScaleRequest{}
		nodeStrs := flagStringArray(args, "--node")
		groupStrs := flagStringArray(args, "--groups")
		sshUser := flagString(args, "--ssh-user", "user")
		zone := flagString(args, "--zone", "")
		capacity := flagString(args, "--capacity", "")

		for i, ns := range nodeStrs {
			h, err := parseNodeStr(ns)
			if err != nil {
				return err
			}
			if h.SSHUser == "" {
				h.SSHUser = sshUser
			}
			if zone != "" {
				h.Zone = zone
			}
			if capacity != "" {
				h.Capacity = capacity
			}
			if i < len(groupStrs) {
				h.Groups = strings.Split(groupStrs[i], ",")
			}
			req.NewHosts = append(req.NewHosts, *h)
		}
	}

	// SSH ключ
	keyFile := flagString(args, "--key-file", "")
	if keyFile != "" {
		pem, err := os.ReadFile(keyFile)
		if err != nil {
			return fmt.Errorf("не удалось прочитать ключ %s: %w", keyFile, err)
		}
		for i := range req.NewHosts {
			if req.NewHosts[i].SSHPrivateKey == "" {
				req.NewHosts[i].SSHPrivateKey = string(pem)
			}
		}
	}

	if len(req.NewHosts) == 0 {
		return fmt.Errorf("нужна хотя бы одна нода (--node или --file)")
	}

	data, err := cl.POST("/clusters/"+id+"/scale", req)
	if err != nil {
		return err
	}
	if cfg.JSON {
		printJSONRaw(data)
		return nil
	}
	var resp AcceptedResponse
	if err := json.Unmarshal(data, &resp); err != nil {
		return err
	}
	fmt.Printf("  %s Scale запущен  job_id: %s\n",
		c(cGreen, "→"), c(cCyan, resp.JobID))
	if watch {
		return watchJob(cl, cfg, resp.JobID)
	}
	fmt.Printf("  Лог: s3ctl job watch %s\n", resp.JobID)
	return nil
}

// ── watchJob ──────────────────────────────────────────────────────────────────

func watchJob(cl *Client, cfg *Config, jobID string) error {
	fmt.Printf("\n  Слежу за задачей %s  (Ctrl+C для выхода)\n", c(cCyan, jobID))
	sep()

	lastStatus := ""
	for {
		data, err := cl.GET("/jobs/" + jobID)
		if err != nil {
			return err
		}
		var job JobResponse
		if err := json.Unmarshal(data, &job); err != nil {
			return err
		}

		if job.Status != lastStatus {
			ts := time.Now().Format("15:04:05")
			fmt.Printf("  [%s] %s\n", c(cGray, ts), statusC(job.Status))
			lastStatus = job.Status
		}

		if job.Status == "success" || job.Status == "failed" {
			fmt.Println()
			if job.Status == "success" {
				fmt.Printf("  %s Завершено успешно\n", c(cGreen, "✓"))
			} else {
				rc := "?"
				if job.ReturnCode != nil {
					rc = fmt.Sprintf("%d", *job.ReturnCode)
				}
				fmt.Printf("  %s Завершено с ошибкой (rc=%s)\n", c(cRed, "✗"), rc)
				// Последние 25 строк лога
				if job.Log != "" {
					lines := strings.Split(job.Log, "\n")
					start := len(lines) - 25
					if start < 0 {
						start = 0
					}
					fmt.Println(c(cGray, "  --- последние строки лога ---"))
					for _, l := range lines[start:] {
						fmt.Println("  " + c(cRed, l))
					}
				}
			}
			return nil
		}
		time.Sleep(3 * time.Second)
	}
}

// ── parseNodeStr ──────────────────────────────────────────────────────────────

// Формат: label,ip[,ssh_user[,ssh_port]]
func parseNodeStr(s string) (*HostSpec, error) {
	parts := strings.Split(s, ",")
	if len(parts) < 2 {
		return nil, fmt.Errorf("--node: ожидается label,ip[,ssh_user[,ssh_port]], получено %q", s)
	}
	h := &HostSpec{
		Label:   strings.TrimSpace(parts[0]),
		IP:      strings.TrimSpace(parts[1]),
		SSHUser: "user",
		SSHPort: 22,
	}
	if len(parts) >= 3 && strings.TrimSpace(parts[2]) != "" {
		h.SSHUser = strings.TrimSpace(parts[2])
	}
	if len(parts) >= 4 {
		port := 0
		fmt.Sscanf(strings.TrimSpace(parts[3]), "%d", &port)
		if port > 0 {
			h.SSHPort = port
		}
	}
	return h, nil
}
