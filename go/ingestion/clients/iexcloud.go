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

const IEXCloudURL = "https://sandbox.iexapis.com/stable/stock/aapl/quote?token=Tpk_eda11ba05d5349c285f46e089b8f1355"

func StreamIEXCloud(ctx context.Context, ch chan<- Packet, counter *int64) {
	client := &http.Client{Timeout: 10 * time.Second}
	ticker := time.NewTicker(10 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			resp, err := client.Get(IEXCloudURL)
			if err != nil {
				log.Printf("IEX Cloud error: %v", err)
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
				Source:    "iexcloud",
				Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
				Data:      data,
			}
			atomic.AddInt64(counter, 1)
		}
	}
}
