package clients

import (
	"context"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"sync/atomic"
	"time"
)

const FinnhubURL = "https://finnhub.io/api/v1/quote?symbol=AAPL&token="

func StreamFinnhub(ctx context.Context, ch chan<- Packet, counter *int64) {
	apiKey := getEnvOrPrompt("FINNHUB_API_KEY", "Enter your Finnhub API key: ")
	if apiKey == "" {
		log.Println("Finnhub: no API key provided, skipping")
		return
	}

	client := &http.Client{Timeout: 10 * time.Second}
	ticker := time.NewTicker(60 * time.Second / 59) // 59 per minute (free tier: 60/min)
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

func StreamFinnhubWithLimit(ctx context.Context, ch chan<- Packet, counter *int64, limit int64, onDone func()) {
	apiKey := getEnvOrPrompt("FINNHUB_API_KEY", "Enter your Finnhub API key: ")
	if apiKey == "" {
		log.Println("Finnhub: no API key provided, skipping")
		onDone()
		return
	}

	client := &http.Client{Timeout: 10 * time.Second}
	ticker := time.NewTicker(60 * time.Second / 59) // 59 per minute (free tier: 60/min)
	defer ticker.Stop()

	url := FinnhubURL + apiKey

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if atomic.LoadInt64(counter) >= limit {
				onDone()
				return
			}
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