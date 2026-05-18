package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

type Client struct {
	BaseURL string
	http    *http.Client
}

func newClient(baseURL string) *Client {
	return &Client{
		BaseURL: baseURL,
		http:    &http.Client{Timeout: 30 * time.Second},
	}
}

func (c *Client) request(method, path string, body interface{}) ([]byte, int, error) {
	var reqBody io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return nil, 0, fmt.Errorf("marshal: %w", err)
		}
		reqBody = bytes.NewReader(data)
	}

	url := c.BaseURL + "/api/v1" + path
	req, err := http.NewRequest(method, url, reqBody)
	if err != nil {
		return nil, 0, fmt.Errorf("create request: %w", err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("connect to %s: %w", c.BaseURL, err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, resp.StatusCode, err
	}
	return data, resp.StatusCode, nil
}

func (c *Client) GET(path string) ([]byte, error) {
	data, code, err := c.request("GET", path, nil)
	if err != nil {
		return nil, err
	}
	if code >= 400 {
		return nil, apiError(code, data)
	}
	return data, nil
}

func (c *Client) POST(path string, body interface{}) ([]byte, error) {
	data, code, err := c.request("POST", path, body)
	if err != nil {
		return nil, err
	}
	if code >= 400 {
		return nil, apiError(code, data)
	}
	return data, nil
}

func (c *Client) DELETE(path string) ([]byte, error) {
	data, code, err := c.request("DELETE", path, nil)
	if err != nil {
		return nil, err
	}
	if code >= 400 {
		return nil, apiError(code, data)
	}
	return data, nil
}

func apiError(code int, body []byte) error {
	// Попытка извлечь detail из JSON
	var e struct {
		Detail interface{} `json:"detail"`
	}
	if json.Unmarshal(body, &e) == nil && e.Detail != nil {
		switch v := e.Detail.(type) {
		case string:
			return fmt.Errorf("HTTP %d: %s", code, v)
		case map[string]interface{}:
			if msg, ok := v["message"].(string); ok {
				return fmt.Errorf("HTTP %d: %s", code, msg)
			}
		}
	}
	return fmt.Errorf("HTTP %d: %s", code, string(body))
}
