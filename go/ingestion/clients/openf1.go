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

type Packet struct {
	Source    string                 `json:"source"`
	Timestamp string                 `json:"timestamp"`
	Data      map[string]interface{} `json:"data"`
}

const OpenF1URL = "https://api.openf1.org/v1/car_data"

func StreamOpenF1(ctx context.Context, ch chan<- Packet, counter *int64) {
	client := &http.Client{Timeout: 10 * time.Second}
	ticker := time.NewTicker(10 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			resp, err := client.Get(OpenF1URL + "?session_key=latest&driver_number=1")
			if err != nil {
				log.Printf("OpenF1 error: %v", err)
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
				Source:    "openf1",
				Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
				Data:      data,
			}
			atomic.AddInt64(counter, 1)
		}
	}
}
