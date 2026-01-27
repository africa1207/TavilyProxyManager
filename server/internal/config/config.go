package config

import (
	"os"
	"strconv"
	"time"
)

type Config struct {
	ListenAddr      string
	DatabasePath    string
	TavilyBaseURL   string
	UpstreamTimeout time.Duration
}

func FromEnv() Config {
	listenAddr := getenv("LISTEN_ADDR", "")
	if listenAddr == "" {
		port := getenv("PORT", "8080")
		listenAddr = ":" + port
	}

	dbPath := getenvFirst("./server/data/app.db", "DB_PATH", "DATABASE_PATH")
	baseURL := getenv("TAVILY_BASE_URL", "https://api.tavily.com")
	timeout := getenvDuration("UPSTREAM_TIMEOUT", 150*time.Second)

	return Config{
		ListenAddr:      listenAddr,
		DatabasePath:    dbPath,
		TavilyBaseURL:   baseURL,
		UpstreamTimeout: timeout,
	}
}

func getenv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func getenvFirst(def string, keys ...string) string {
	for _, key := range keys {
		if v := os.Getenv(key); v != "" {
			return v
		}
	}
	return def
}

func getenvDuration(key string, def time.Duration) time.Duration {
	if v := os.Getenv(key); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			return d
		}
		if seconds, err := strconv.Atoi(v); err == nil {
			return time.Duration(seconds) * time.Second
		}
	}
	return def
}
