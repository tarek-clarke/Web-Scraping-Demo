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

const WeatherURL = "https://api.openweathermap.org/data/2.5/weather?q=Tallinn,EE&appid="

var WeatherAPIKey = ""

func StreamOpenWeather(ctx context.Context, ch chan<- Packet, counter *int64) {
	if WeatherAPIKey == "" {
		WeatherAPIKey = getEnvOrPrompt("OPENWEATHER_API_KEY", "Enter your OpenWeatherMap API key: ")
		if WeatherAPIKey == "" {
			log.Println("OpenWeather: no API key, skipping")
			return
		}
	}

	client := &http.Client{Timeout: 10 * time.Second}
	ticker := time.NewTicker(60 * time.Second / 59) // 59 per minute = ~1.017 sec/call
	defer ticker.Stop()

	url := WeatherURL + WeatherAPIKey

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			resp, err := client.Get(url)
			if err != nil {
				log.Printf("OpenWeather error: %v", err)
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

			if data["cod"] != nil && data["cod"] != "200" {
				continue
			}

			ch <- Packet{
				Source:    "openweather",
				Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
				Data:      data,
			}
			atomic.AddInt64(counter, 1)
		}
	}
}

func StreamOpenWeatherWithLimit(ctx context.Context, ch chan<- Packet, counter *int64, limit int64, onDone func()) {
	if WeatherAPIKey == "" {
		WeatherAPIKey = getEnvOrPrompt("OPENWEATHER_API_KEY", "Enter your OpenWeatherMap API key: ")
		if WeatherAPIKey == "" {
			log.Println("OpenWeather: no API key, skipping")
			onDone()
			return
		}
	}

	client := &http.Client{Timeout: 10 * time.Second}
	ticker := time.NewTicker(60 * time.Second / 59) // 59 per minute = ~1.017 sec/call
	defer ticker.Stop()

	url := WeatherURL + WeatherAPIKey

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
				log.Printf("OpenWeather error: %v", err)
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

			if data["cod"] != nil && data["cod"] != "200" {
				continue
			}

			ch <- Packet{
				Source:    "openweather",
				Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
				Data:      data,
			}
			atomic.AddInt64(counter, 1)
		}
	}
}