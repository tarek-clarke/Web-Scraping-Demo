package clients

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"sync/atomic"
	"time"
)

const FinnhubURL = "https://finnhub.io/api/v1/quote?symbol=AAPL&token="

func StreamFinnhub(ctx context.Context, ch chan<- Packet, counter *int64) {
	apiKey := getFinnhubAPIKey()
	if apiKey == "" {
		log.Println("Finnhub: no API key provided, skipping")
		return
	}

	client := &http.Client{Timeout: 10 * time.Second}
	ticker := time.NewTicker(10 * time.Millisecond)
	defer ticker.Stop()

	url := FinnhubURL + apiKey

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			resp, err := client.Get(url)
			if err != nil {
				log.Printf("Finnhub error: %v", err)
				continue
			}

			body, err := io.ReadAll(resp.Body)
			resp.Body.Close()
			if err != nil {
				continue
			}

			var data map[string]interface{}
			if err := json.Unmarshal(body, &data); err != nil {
				continue
			}

			if data["c"] == nil {
				continue
			}

			ch <- Packet{
				Source:    "finnhub",
				Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
				Data:      data,
			}
			atomic.AddInt64(counter, 1)
		}
	}
}

func getFinnhubAPIKey() string {
	envKey := os.Getenv("FINNHUB_API_KEY")
	if envKey != "" {
		return envKey
	}

	fmt.Print("Enter your Finnhub API key: ")
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