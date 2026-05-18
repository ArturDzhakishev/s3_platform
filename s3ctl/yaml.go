package main

import (
	"strconv"
	"strings"
)

// Минималистичный YAML-парсер для форматов кластера и scale.
// Поддерживает: строки, числа, булевы, списки, вложенные объекты.
// Не поддерживает: якоря, многострочные значения, сложные типы.

// yamlGetString извлекает строковое значение по ключу из YAML-данных.
func yamlGetString(data []byte, key string) string {
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, key+":") {
			val := strings.TrimSpace(strings.TrimPrefix(line, key+":"))
			val = strings.Trim(val, `"'`)
			return val
		}
	}
	return ""
}

// parseClusterYAML разбирает YAML-файл кластера в CreateClusterRequest.
func parseClusterYAML(data []byte, req *CreateClusterRequest) error {
	lines := strings.Split(string(data), "\n")
	req.ExtraVars = make(map[string]interface{})

	section := "" // "hosts", "extra_vars"
	var curHost *HostSpec

	for _, rawLine := range lines {
		// Убрать комментарии
		if idx := strings.Index(rawLine, " #"); idx >= 0 {
			rawLine = rawLine[:idx]
		}
		line := strings.TrimRight(rawLine, " \t\r")
		if strings.TrimSpace(line) == "" {
			continue
		}

		indent := countIndent(line)
		trimmed := strings.TrimSpace(line)

		switch {
		// Верхний уровень (indent == 0)
		case indent == 0:
			section = ""
			curHost = nil
			if kv := splitKV(trimmed); kv != nil {
				switch kv[0] {
				case "name":
					req.Name = unquote(kv[1])
				case "engine":
					req.Engine = unquote(kv[1])
				case "hosts":
					section = "hosts"
				case "extra_vars":
					section = "extra_vars"
				}
			}

		// Уровень секции (indent == 2)
		case indent == 2:
			if section == "hosts" {
				if strings.HasPrefix(trimmed, "- ") {
					// Новый хост
					h := HostSpec{SSHUser: "user", SSHPort: 22, Role: "worker"}
					req.Hosts = append(req.Hosts, h)
					curHost = &req.Hosts[len(req.Hosts)-1]
					// Поле на той же строке что и "-"
					kv := splitKV(strings.TrimPrefix(trimmed, "- "))
					if kv != nil {
						applyHostField(curHost, kv[0], kv[1])
					}
				} else if curHost != nil {
					if kv := splitKV(trimmed); kv != nil {
						applyHostField(curHost, kv[0], kv[1])
					}
				}
			} else if section == "extra_vars" {
				if kv := splitKV(trimmed); kv != nil {
					req.ExtraVars[kv[0]] = parseValue(kv[1])
				}
			}

		// Уровень полей хоста (indent == 4 или 6)
		case indent >= 4 && section == "hosts" && curHost != nil:
			trimmed2 := strings.TrimSpace(line)
			// groups: [a, b, c] или groups: на отдельной строке
			if strings.HasPrefix(trimmed2, "- ") {
				// Элемент списка groups
				val := unquote(strings.TrimPrefix(trimmed2, "- "))
				curHost.Groups = append(curHost.Groups, val)
			} else if kv := splitKV(trimmed2); kv != nil {
				applyHostField(curHost, kv[0], kv[1])
			}
		}
	}

	// Расставить роли: первый хост — master
	for i := range req.Hosts {
		if i == 0 && req.Hosts[i].Role == "worker" {
			req.Hosts[i].Role = "master"
		}
	}

	return nil
}

// parseScaleYAML разбирает YAML-файл scale в ScaleRequest.
func parseScaleYAML(data []byte, req *ScaleRequest) error {
	lines := strings.Split(string(data), "\n")
	inNewHosts := false
	var curHost *HostSpec

	for _, rawLine := range lines {
		if idx := strings.Index(rawLine, " #"); idx >= 0 {
			rawLine = rawLine[:idx]
		}
		line := strings.TrimRight(rawLine, " \t\r")
		if strings.TrimSpace(line) == "" {
			continue
		}

		indent := countIndent(line)
		trimmed := strings.TrimSpace(line)

		switch {
		case indent == 0:
			if kv := splitKV(trimmed); kv != nil && kv[0] == "new_hosts" {
				inNewHosts = true
			} else {
				inNewHosts = false
			}
		case indent == 2 && inNewHosts:
			if strings.HasPrefix(trimmed, "- ") {
				h := HostSpec{SSHUser: "user", SSHPort: 22, Role: "worker"}
				req.NewHosts = append(req.NewHosts, h)
				curHost = &req.NewHosts[len(req.NewHosts)-1]
				kv := splitKV(strings.TrimPrefix(trimmed, "- "))
				if kv != nil {
					applyHostField(curHost, kv[0], kv[1])
				}
			} else if curHost != nil {
				if kv := splitKV(trimmed); kv != nil {
					applyHostField(curHost, kv[0], kv[1])
				}
			}
		case indent >= 4 && inNewHosts && curHost != nil:
			trimmed2 := strings.TrimSpace(line)
			if strings.HasPrefix(trimmed2, "- ") {
				val := unquote(strings.TrimPrefix(trimmed2, "- "))
				curHost.Groups = append(curHost.Groups, val)
			} else if kv := splitKV(trimmed2); kv != nil {
				applyHostField(curHost, kv[0], kv[1])
			}
		}
	}
	return nil
}

// ── helpers ───────────────────────────────────────────────────────────────────

func applyHostField(h *HostSpec, key, val string) {
	val = unquote(val)
	switch key {
	case "label":
		h.Label = val
	case "ip":
		h.IP = val
	case "ssh_user":
		h.SSHUser = val
	case "ssh_port":
		if p, err := strconv.Atoi(val); err == nil {
			h.SSHPort = p
		}
	case "role":
		h.Role = val
	case "zone":
		h.Zone = val
	case "capacity":
		h.Capacity = val
	case "groups":
		// Inline list: [a, b, c]
		if strings.HasPrefix(val, "[") {
			inner := strings.Trim(val, "[]")
			for _, g := range strings.Split(inner, ",") {
				g = strings.TrimSpace(unquote(g))
				if g != "" {
					h.Groups = append(h.Groups, g)
				}
			}
		}
	}
}

func splitKV(s string) []string {
	idx := strings.Index(s, ":")
	if idx < 0 {
		return nil
	}
	key := strings.TrimSpace(s[:idx])
	val := strings.TrimSpace(s[idx+1:])
	if key == "" {
		return nil
	}
	return []string{key, val}
}

func unquote(s string) string {
	s = strings.TrimSpace(s)
	if len(s) >= 2 {
		if (s[0] == '"' && s[len(s)-1] == '"') ||
			(s[0] == '\'' && s[len(s)-1] == '\'') {
			return s[1 : len(s)-1]
		}
	}
	return s
}

func parseValue(s string) interface{} {
	s = unquote(s)
	if s == "true" {
		return true
	}
	if s == "false" {
		return false
	}
	if n, err := strconv.ParseInt(s, 10, 64); err == nil {
		return n
	}
	if f, err := strconv.ParseFloat(s, 64); err == nil {
		return f
	}
	return s
}

func countIndent(s string) int {
	count := 0
	for _, c := range s {
		if c == ' ' {
			count++
		} else if c == '\t' {
			count += 2
		} else {
			break
		}
	}
	return count
}
