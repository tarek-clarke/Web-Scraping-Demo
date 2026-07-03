package clients

import (
	"context"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync/atomic"
	"time"
)

const OpenF1URL = "https://api.openf1.org/v1/car_data"
const TokenURL = "https://api.openf1.org/token"

// getAuthToken checks for credentials and returns an access token if possible.
func getAuthToken() string {
	email := os.Getenv("OPENF1_EMAIL")
	password := os.Getenv("OPENF1_PASSWORD")
	if email == "" || password == "" {
		return ""
	}

	client := &http.Client{Timeout: 10 * time.Second}
	data := url.Values{}
	data.Set("username", email)
	data.Set("password", password)

	req, err := http.NewRequest("POST", TokenURL, strings.NewReader(data.Encode()))
	if err != nil {
		log.Printf("[OpenF1 Auth] Failed to create request: %v", err)
		return ""
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := client.Do(req)
	if err != nil {
		log.Printf("[OpenF1 Auth] Failed to fetch token: %v", err)
		return ""
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		log.Printf("[OpenF1 Auth] Token endpoint returned status %d: %s", resp.StatusCode, string(body))
		return ""
	}

	var result struct {
		AccessToken string `json:"access_token"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		log.Printf("[OpenF1 Auth] Failed to decode token response: %v", err)
		return ""
	}

	return result.AccessToken
}

func doRequest(client *http.Client, urlStr string, token string) (*http.Response, error) {
	req, err := http.NewRequest("GET", urlStr, nil)
	if err != nil {
		return nil, err
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	return client.Do(req)
}

func StreamOpenF1(ctx context.Context, ch chan<- Packet, counter *int64) {
	client := &http.Client{Timeout: 30 * time.Second}
	ticker := time.NewTicker(1 * time.Second) // Poll every 1 second (60 times per minute)
	defer ticker.Stop()

	token := getAuthToken()
	if token != "" {
		log.Println("[OpenF1] Successfully authenticated live session access.")
	} else {
		log.Println("[OpenF1] No credentials found. Running in unauthenticated mode.")
	}

	// Initialize lastTime to 10 seconds ago to grab the initial window
	lastTime := time.Now().UTC().Add(-10 * time.Second).Format("2006-01-02T15:04:05")

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			urlStr := OpenF1URL + "?session_key=latest"
			if lastTime != "" {
				urlStr += "&date>" + url.QueryEscape(lastTime)
			}

			resp, err := doRequest(client, urlStr, token)
			if err != nil {
				log.Printf("OpenF1 error: %v", err)
				continue
			}

			body, err := io.ReadAll(resp.Body)
			resp.Body.Close()
			if err != nil {
				continue
			}

			if resp.StatusCode == http.StatusUnauthorized {
				log.Println("[OpenF1] Token expired or unauthorized. Attempting to refresh...")
				token = getAuthToken()
				continue
			}

			var rawList []map[string]interface{}
			if err := json.Unmarshal(body, &rawList); err != nil {
				var rawObj map[string]interface{}
				if err := json.Unmarshal(body, &rawObj); err == nil {
					ch <- Packet{
						Source:    "openf1",
						Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
						Data:      rawObj,
					}
					atomic.AddInt64(counter, 1)

					if dateVal, ok := rawObj["date"].(string); ok {
						dateStr := dateVal
						if idx := strings.Index(dateStr, "+"); idx != -1 {
							dateStr = dateStr[:idx]
						}
						if idx := strings.Index(dateStr, "Z"); idx != -1 {
							dateStr = dateStr[:idx]
						}
						if dateStr > lastTime {
							lastTime = dateStr
						}
					}
				}
				continue
			}

			for _, data := range rawList {
				ch <- Packet{
					Source:    "openf1",
					Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
					Data:      data,
				}
				atomic.AddInt64(counter, 1)

				if dateVal, ok := data["date"].(string); ok {
					dateStr := dateVal
					if idx := strings.Index(dateStr, "+"); idx != -1 {
						dateStr = dateStr[:idx]
					}
					if idx := strings.Index(dateStr, "Z"); idx != -1 {
						dateStr = dateStr[:idx]
					}
					if dateStr > lastTime {
						lastTime = dateStr
					}
				}
			}
		}
	}
}

func StreamOpenF1WithLimit(ctx context.Context, ch chan<- Packet, counter *int64, limit int64, onDone func()) {
	client := &http.Client{Timeout: 10 * time.Second}
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	token := getAuthToken()
	if token != "" {
		log.Println("[OpenF1] Successfully authenticated live session access (limited mode).")
	} else {
		log.Println("[OpenF1] No credentials found. Running in unauthenticated mode.")
	}

	lastTime := time.Now().UTC().Add(-10 * time.Second).Format("2006-01-02T15:04:05")

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if atomic.LoadInt64(counter) >= limit {
				onDone()
				return
			}

			urlStr := OpenF1URL + "?session_key=latest"
			if lastTime != "" {
				urlStr += "&date>" + url.QueryEscape(lastTime)
			}

			resp, err := doRequest(client, urlStr, token)
			if err != nil {
				log.Printf("OpenF1 error: %v", err)
				continue
			}

			body, err := io.ReadAll(resp.Body)
			resp.Body.Close()
			if err != nil {
				continue
			}

			if resp.StatusCode == http.StatusUnauthorized {
				log.Println("[OpenF1] Token expired or unauthorized. Attempting to refresh...")
				token = getAuthToken()
				continue
			}

			var rawList []map[string]interface{}
			if err := json.Unmarshal(body, &rawList); err != nil {
				var rawObj map[string]interface{}
				if err := json.Unmarshal(body, &rawObj); err == nil {
					if atomic.LoadInt64(counter) < limit {
						ch <- Packet{
							Source:    "openf1",
							Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
							Data:      rawObj,
						}
						atomic.AddInt64(counter, 1)

						if dateVal, ok := rawObj["date"].(string); ok {
							dateStr := dateVal
							if idx := strings.Index(dateStr, "+"); idx != -1 {
								dateStr = dateStr[:idx]
							}
							if idx := strings.Index(dateStr, "Z"); idx != -1 {
								dateStr = dateStr[:idx]
							}
							if dateStr > lastTime {
								lastTime = dateStr
							}
						}
					}
				}
				continue
			}

			for _, data := range rawList {
				if atomic.LoadInt64(counter) >= limit {
					onDone()
					return
				}
				ch <- Packet{
					Source:    "openf1",
					Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
					Data:      data,
				}
				atomic.AddInt64(counter, 1)

				if dateVal, ok := data["date"].(string); ok {
					dateStr := dateVal
					if idx := strings.Index(dateStr, "+"); idx != -1 {
						dateStr = dateStr[:idx]
					}
					if idx := strings.Index(dateStr, "Z"); idx != -1 {
						dateStr = dateStr[:idx]
					}
					if dateStr > lastTime {
						lastTime = dateStr
					}
				}
			}
		}
	}
}
