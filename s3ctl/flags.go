package main

import (
	"strconv"
	"strings"
)

// flagString ищет флаг вида --name value или --name=value
func flagString(args []string, name, def string) string {
	for i, a := range args {
		if a == name {
			if i+1 < len(args) {
				return args[i+1]
			}
			return def
		}
		if strings.HasPrefix(a, name+"=") {
			return strings.TrimPrefix(a, name+"=")
		}
	}
	return def
}

// flagBool ищет флаг-переключатель --name
func flagBool(args []string, name string) bool {
	for _, a := range args {
		if a == name {
			return true
		}
	}
	return false
}

// flagInt ищет флаг вида --name value и возвращает int
func flagInt(args []string, name string, def int) int {
	s := flagString(args, name, "")
	if s == "" {
		return def
	}
	n, err := strconv.Atoi(s)
	if err != nil {
		return def
	}
	return n
}

// flagStringArray собирает все вхождения --name value (можно повторять)
func flagStringArray(args []string, name string) []string {
	var result []string
	for i, a := range args {
		if a == name {
			if i+1 < len(args) {
				result = append(result, args[i+1])
			}
		} else if strings.HasPrefix(a, name+"=") {
			result = append(result, strings.TrimPrefix(a, name+"="))
		}
	}
	return result
}
