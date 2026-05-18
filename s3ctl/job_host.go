package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

// ── job ───────────────────────────────────────────────────────────────────────

func jobCommand(cl *Client, cfg *Config, args []string) error {
	if len(args) == 0 {
		fmt.Println("Подкоманды: list, get, log, watch")
		return nil
	}
	switch args[0] {
	case "list", "ls":
		return cmdJobList(cl, cfg, args[1:])
	case "get":
		return cmdJobGet(cl, cfg, args[1:])
	case "log":
		return cmdJobLog(cl, cfg, args[1:])
	case "watch":
		return cmdJobWatch(cl, cfg, args[1:])
	default:
		return fmt.Errorf("неизвестная подкоманда job %q", args[0])
	}
}

func cmdJobList(cl *Client, cfg *Config, args []string) error {
	status := flagString(args, "--status", "")
	limit := flagInt(args, "--limit", 20)

	path := fmt.Sprintf("/jobs?limit=%d", limit)
	if status != "" {
		path += "&status=" + status
	}

	data, err := cl.GET(path)
	if err != nil {
		return err
	}
	if cfg.JSON {
		printJSONRaw(data)
		return nil
	}
	var jobs []JobResponse
	if err := json.Unmarshal(data, &jobs); err != nil {
		return err
	}
	if len(jobs) == 0 {
		fmt.Println("Задач нет.")
		return nil
	}
	hdr(fmt.Sprintf("Задачи (%d)", len(jobs)))
	for _, j := range jobs {
		printJob(j)
		sep()
	}
	return nil
}

func cmdJobGet(cl *Client, cfg *Config, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("job get <job-id>")
	}
	data, err := cl.GET("/jobs/" + args[0])
	if err != nil {
		return err
	}
	if cfg.JSON {
		printJSONRaw(data)
		return nil
	}
	var j JobResponse
	if err := json.Unmarshal(data, &j); err != nil {
		return err
	}
	hdr("Задача")
	printJob(j)
	return nil
}

func cmdJobLog(cl *Client, cfg *Config, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("job log <job-id>")
	}
	raw := flagBool(args, "--raw")

	data, err := cl.GET("/jobs/" + args[0])
	if err != nil {
		return err
	}
	var j JobResponse
	if err := json.Unmarshal(data, &j); err != nil {
		return err
	}
	if j.Log == "" {
		fmt.Println(c(cGray, "Лог пуст"))
		return nil
	}
	hdr(fmt.Sprintf("Лог %s  [%s]", shortID(args[0]), j.Status))
	if raw || cfg.JSON {
		fmt.Println(j.Log)
	} else {
		printAnsibleLog(j.Log)
	}
	return nil
}

func cmdJobWatch(cl *Client, cfg *Config, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("job watch <job-id>")
	}
	return watchJob(cl, cfg, args[0])
}

// ── host ──────────────────────────────────────────────────────────────────────

func hostCommand(cl *Client, cfg *Config, args []string) error {
	if len(args) == 0 {
		fmt.Println("Подкоманды: list, ping")
		return nil
	}
	switch args[0] {
	case "list", "ls":
		return cmdHostList(cl, cfg, args[1:])
	case "ping":
		return cmdHostPing(cl, cfg, args[1:])
	default:
		return fmt.Errorf("неизвестная подкоманда host %q", args[0])
	}
}

func cmdHostList(cl *Client, cfg *Config, args []string) error {
	status := flagString(args, "--status", "")
	path := "/hosts"
	if status != "" {
		path += "?status=" + status
	}

	data, err := cl.GET(path)
	if err != nil {
		return err
	}
	if cfg.JSON {
		printJSONRaw(data)
		return nil
	}
	var hosts []HostResponse
	if err := json.Unmarshal(data, &hosts); err != nil {
		return err
	}
	if len(hosts) == 0 {
		fmt.Println("Хостов нет.")
		return nil
	}
	hdr(fmt.Sprintf("Хосты (%d)", len(hosts)))
	for _, h := range hosts {
		cl := c(cGray, "—")
		if h.ClusterID != "" {
			cl = shortID(h.ClusterID)
		}
		fmt.Printf("  %-16s  %-16s  %-8s  %-14s  cluster: %s\n",
			c(cBold, h.Label), c(cCyan, h.IP),
			h.Role, statusC(h.Status), cl)
	}
	return nil
}

func cmdHostPing(cl *Client, cfg *Config, args []string) error {
	ip := flagString(args, "--ip", "")
	user := flagString(args, "--ssh-user", "user")
	port := flagInt(args, "--ssh-port", 22)
	keyFile := flagString(args, "--key-file", "")

	if ip == "" {
		return fmt.Errorf("--ip обязателен")
	}

	body := map[string]interface{}{
		"ip":       ip,
		"ssh_user": user,
		"ssh_port": port,
	}
	if keyFile != "" {
		pem, err := os.ReadFile(keyFile)
		if err != nil {
			return fmt.Errorf("не удалось прочитать ключ: %w", err)
		}
		body["ssh_private_key"] = string(pem)
	}

	data, err := cl.POST("/ping", body)
	if err != nil {
		return err
	}
	if cfg.JSON {
		printJSONRaw(data)
		return nil
	}
	var res struct {
		Reachable bool    `json:"reachable"`
		PingMs    float64 `json:"ping_ms"`
		Error     string  `json:"error"`
	}
	if err := json.Unmarshal(data, &res); err != nil {
		return err
	}
	if res.Reachable {
		fmt.Printf("  %s  %s  %.1f ms\n",
			c(cGreen, "✓ Доступен"), c(cCyan, ip), res.PingMs)
	} else {
		fmt.Printf("  %s  %s  %s\n",
			c(cRed, "✗ Недоступен"), c(cCyan, ip), c(cRed, res.Error))
	}
	return nil
}

// ── playbooks ─────────────────────────────────────────────────────────────────

func cmdPlaybooks(cl *Client, cfg *Config) error {
	data, err := cl.GET("/playbooks")
	if err != nil {
		return err
	}
	if cfg.JSON {
		printJSONRaw(data)
		return nil
	}
	var res struct {
		Playbooks    []string `json:"playbooks"`
		PlaybooksDir string   `json:"playbooks_dir"`
	}
	if err := json.Unmarshal(data, &res); err != nil {
		return err
	}
	hdr(fmt.Sprintf("Плейбуки (%s)", res.PlaybooksDir))
	for _, p := range res.Playbooks {
		parts := strings.Split(p, "/")
		if len(parts) >= 2 {
			fmt.Printf("  %-12s  %s\n",
				engineC(parts[0]), c(cCyan, parts[len(parts)-1]))
		} else {
			fmt.Printf("  %s\n", p)
		}
	}
	return nil
}
