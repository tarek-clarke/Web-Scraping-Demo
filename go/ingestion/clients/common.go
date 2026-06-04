package clients

import (
	"bufio"
	"fmt"
	"os"
)

type Packet struct {
	Source    string                 `json:"source"`
	Timestamp string                 `json:"timestamp"`
	Data      map[string]interface{} `json:"data"`
}

func getEnvOrPrompt(envVar string, prompt string) string {
	envKey := os.Getenv(envVar)
	if envKey != "" {
		return envKey
	}

	fmt.Print(prompt)
	reader := bufio.NewReader(os.Stdin)
	key, err := reader.ReadString('\n')
	if err != nil {
		return ""
	}
	return trimNewline(key)
}

func trimNewline(s string) string {
	for len(s) > 0 && (s[len(s)-1] == '\n' || s[len(s)-1] == '\r') {
		s = s[:len(s)-1]
	}
	return s
}