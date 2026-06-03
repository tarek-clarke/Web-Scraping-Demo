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

const OpenMeteoURL = "https://api.open-meteo.com/v1/forecast?latitude=59.4370&longitude=24.7536&current_weather=true"

func StreamOpenMeteo(ctx context.Context, ch chan<- Packet, counter *int64) {
	client := &http.Client{Timeout: 10 * time.Second}
	ticker := time.NewTicker(10 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			resp, err := client.Get(OpenMeteoURL)
			if err != nil {
				log.Printf("OpenMeteo error: %v", err)
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

			ch <- Packet{
				Source:    "openmeteo",
				Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
				Data:      data,
			}
			atomic.AddInt64(counter, 1)
		}
	}
}
