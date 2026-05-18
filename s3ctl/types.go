package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

// ── Запросы ───────────────────────────────────────────────────────────────────

type HostSpec struct {
	Label         string   `json:"label"`
	IP            string   `json:"ip"`
	SSHUser       string   `json:"ssh_user"`
	SSHPort       int      `json:"ssh_port"`
	SSHPrivateKey string   `json:"ssh_private_key,omitempty"`
	Role          string   `json:"role,omitempty"`
	Groups        []string `json:"groups,omitempty"`
	Zone          string   `json:"zone,omitempty"`
	Capacity      string   `json:"capacity,omitempty"`
}

type CreateClusterRequest struct {
	Name      string                 `json:"name"`
	Engine    string                 `json:"engine"`
	Hosts     []HostSpec             `json:"hosts"`
	ExtraVars map[string]interface{} `json:"extra_vars"`
}

type ScaleRequest struct {
	NewHosts []HostSpec `json:"new_hosts"`
}

// ── Ответы ────────────────────────────────────────────────────────────────────

type ClusterResponse struct {
	ClusterID   string                 `json:"cluster_id"`
	Name        string                 `json:"name"`
	Engine      string                 `json:"engine"`
	Status      string                 `json:"status"`
	NodeCount   int                    `json:"node_count"`
	S3Endpoint  string                 `json:"s3_endpoint"`
	Credentials map[string]interface{} `json:"credentials"`
	ErrorMsg    string                 `json:"error_msg"`
	CreatedAt   string                 `json:"created_at"`
	UpdatedAt   string                 `json:"updated_at"`
}

type JobResponse struct {
	JobID      string `json:"job_id"`
	ClusterID  string `json:"cluster_id"`
	JobType    string `json:"job_type"`
	Status     string `json:"status"`
	Playbook   string `json:"playbook"`
	ReturnCode *int   `json:"return_code"`
	Log        string `json:"log"`
	CreatedAt  string `json:"created_at"`
	StartedAt  string `json:"started_at"`
	FinishedAt string `json:"finished_at"`
}

type AcceptedResponse struct {
	JobID     string `json:"job_id"`
	ClusterID string `json:"cluster_id"`
	Status    string `json:"status"`
	Playbook  string `json:"playbook"`
	Message   string `json:"message"`
}

type HostResponse struct {
	HostID    string `json:"host_id"`
	Label     string `json:"label"`
	IP        string `json:"ip"`
	SSHUser   string `json:"ssh_user"`
	SSHPort   int    `json:"ssh_port"`
	Role      string `json:"role"`
	Status    string `json:"status"`
	ClusterID string `json:"cluster_id"`
	Zone      string `json:"zone"`
	Capacity  string `json:"capacity"`
}

// ── Загрузка из файла ─────────────────────────────────────────────────────────

// Файл кластера (YAML или JSON):
//
//	name:   prod-seaweedfs
//	engine: seaweedfs
//	hosts:
//	  - label: node1
//	    ip: 192.168.1.110
//	    ssh_user: user
//	    ssh_port: 22
//	    groups: [seaweedfs, s3, loadbalancer]
//	extra_vars:
//	  seaweedfs_version: "3.63"
func LoadClusterFile(path string) (*CreateClusterRequest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("не удалось прочитать %s: %w", path, err)
	}

	// Попробовать JSON
	var req CreateClusterRequest
	if strings.HasSuffix(path, ".json") {
		if err := json.Unmarshal(data, &req); err != nil {
			return nil, fmt.Errorf("ошибка JSON: %w", err)
		}
	} else {
		// YAML → разобрать вручную через наш минималистичный парсер
		if err := parseClusterYAML(data, &req); err != nil {
			// Fallback на JSON если yaml не сработал
			if err2 := json.Unmarshal(data, &req); err2 != nil {
				return nil, fmt.Errorf("не удалось разобрать файл: %v", err)
			}
		}
	}

	if req.Engine == "" {
		return nil, fmt.Errorf("engine обязателен в файле")
	}
	if len(req.Hosts) == 0 {
		return nil, fmt.Errorf("hosts не может быть пустым")
	}
	return &req, nil
}

// LoadScaleFile читает файл для scale:
//
//	new_hosts:
//	  - label: node4
//	    ip: 192.168.1.113
//	    ssh_user: user
//	    groups: [seaweedfs, s3]
func LoadScaleFile(path string) (*ScaleRequest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("не удалось прочитать %s: %w", path, err)
	}

	var req ScaleRequest
	if strings.HasSuffix(path, ".json") {
		if err := json.Unmarshal(data, &req); err != nil {
			return nil, err
		}
	} else {
		if err := parseScaleYAML(data, &req); err != nil {
			if err2 := json.Unmarshal(data, &req); err2 != nil {
				return nil, fmt.Errorf("не удалось разобрать файл: %v", err)
			}
		}
	}

	if len(req.NewHosts) == 0 {
		return nil, fmt.Errorf("new_hosts не может быть пустым")
	}
	return &req, nil
}
