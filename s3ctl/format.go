package main

import (
	"encoding/json"
	"fmt"
	"strings"
)

const (
	cReset  = "\033[0m"
	cRed    = "\033[31m"
	cGreen  = "\033[32m"
	cYellow = "\033[33m"
	cBlue   = "\033[34m"
	cPurple = "\033[35m"
	cCyan   = "\033[36m"
	cGray   = "\033[90m"
	cBold   = "\033[1m"
)

var noColorMode = false

func c(color, text string) string {
	if noColorMode {
		return text
	}
	return color + text + cReset
}

func statusC(s string) string {
	switch s {
	case "ready", "success":
		return c(cGreen, s)
	case "deploying", "scaling", "running", "pending":
		return c(cYellow, s)
	case "deleting":
		return c(cCyan, s)
	case "failed":
		return c(cRed, s)
	case "available":
		return c(cGreen, s)
	case "in_use":
		return c(cYellow, s)
	case "unreachable":
		return c(cRed, s)
	default:
		return c(cGray, s)
	}
}

func engineC(e string) string {
	switch e {
	case "ceph":
		return c(cBlue, e)
	case "seaweedfs":
		return c(cCyan, e)
	case "garage":
		return c(cPurple, e)
	}
	return e
}

func sep() {
	fmt.Println(c(cGray, strings.Repeat("─", 60)))
}

func hdr(text string) {
	fmt.Println()
	fmt.Println(c(cBold, text))
	sep()
}

func printCluster(cl ClusterResponse) {
	id := cl.ClusterID
	if len(id) > 8 {
		id = id[:8] + "…"
	}
	fmt.Printf("  ID:      %s\n", c(cBold, cl.ClusterID))
	fmt.Printf("  Name:    %s\n", c(cBold, cl.Name))
	fmt.Printf("  Engine:  %s\n", engineC(cl.Engine))
	fmt.Printf("  Status:  %s\n", statusC(cl.Status))
	fmt.Printf("  Nodes:   %d\n", cl.NodeCount)
	if cl.S3Endpoint != "" {
		fmt.Printf("  S3:      %s\n", c(cBlue, cl.S3Endpoint))
	}
	if cl.Credentials != nil {
		fmt.Printf("  %s\n", c(cBold, "Credentials:"))
		if ak, ok := cl.Credentials["access_key"].(string); ok {
			fmt.Printf("    access_key: %s\n", c(cGreen, ak))
		}
		if sk, ok := cl.Credentials["secret_key"].(string); ok {
			fmt.Printf("    secret_key: %s\n", c(cYellow, sk))
		}
		if user, ok := cl.Credentials["user"].(string); ok && user != "" {
			fmt.Printf("    user:       %s\n", user)
		}
	}
	if cl.ErrorMsg != "" {
		fmt.Printf("  Error:   %s\n", c(cRed, cl.ErrorMsg))
	}
	fmt.Printf("  Created: %s\n", c(cGray, cl.CreatedAt))
	_ = id
}

func printJob(j JobResponse) {
	id := j.JobID
	if len(id) > 8 {
		id = id[:8] + "…"
	}
	fmt.Printf("  ID:       %s\n", c(cBold, id))
	fmt.Printf("  Cluster:  %s\n", c(cGray, shortID(j.ClusterID)))
	fmt.Printf("  Type:     %s\n", j.JobType)
	fmt.Printf("  Playbook: %s\n", c(cCyan, j.Playbook))
	fmt.Printf("  Status:   %s\n", statusC(j.Status))
	if j.ReturnCode != nil {
		rc := *j.ReturnCode
		if rc == 0 {
			fmt.Printf("  RC:       %s\n", c(cGreen, "0"))
		} else {
			fmt.Printf("  RC:       %s\n", c(cRed, fmt.Sprintf("%d", rc)))
		}
	}
	if j.StartedAt != "" {
		fmt.Printf("  Started:  %s\n", c(cGray, j.StartedAt))
	}
	if j.FinishedAt != "" {
		fmt.Printf("  Finished: %s\n", c(cGray, j.FinishedAt))
	}
}

func printAnsibleLog(log string) {
	for _, line := range strings.Split(log, "\n") {
		switch {
		case strings.HasPrefix(line, "PLAY "):
			fmt.Println(c(cBlue+cBold, line))
		case strings.HasPrefix(line, "TASK "):
			fmt.Println(c(cPurple, line))
		case strings.HasPrefix(line, "PLAY RECAP"):
			fmt.Println(c(cYellow+cBold, line))
		case strings.Contains(line, "ok:") || strings.Contains(line, "changed:"):
			fmt.Println(c(cGreen, line))
		case strings.Contains(line, "FAILED") || strings.Contains(line, "fatal:") ||
			strings.Contains(line, "ERROR") || strings.Contains(line, "unreachable"):
			fmt.Println(c(cRed, line))
		case strings.Contains(line, "skipping:"):
			fmt.Println(c(cGray, line))
		default:
			fmt.Println(line)
		}
	}
}

func printJSONRaw(data []byte) {
	var v interface{}
	if err := json.Unmarshal(data, &v); err != nil {
		fmt.Println(string(data))
		return
	}
	out, _ := json.MarshalIndent(v, "", "  ")
	fmt.Println(string(out))
}

func shortID(id string) string {
	if len(id) > 8 {
		return id[:8] + "…"
	}
	return id
}
