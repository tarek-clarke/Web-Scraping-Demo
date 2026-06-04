package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"resilient-rap/ingestion/clients"
	"sync"
	"sync/atomic"
	"time"
)

const (
	TargetPackets     = 10000
	TargetPerAPI      = 2500
	TargetHz          = 100
	OutputDir         = "../../data/ingested"
	ProgressInterval  = 10 * time.Second
)

func main() {
	os.MkdirAll(OutputDir, 0755)

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Minute)
	defer cancel()

	packetChan := make(chan clients.Packet, 10000)

	var (
		totalPackets     int64
		openf1Count      int64
		finnhubCount     int64
		spacexCount      int64
		openweatherCount int64
	)

	isAPIDone := map[string]bool{
		"openf1":      false,
		"finnhub":      false,
		"spacex":       false,
		"openweather":  false,
	}

	var doneMu sync.Mutex

	isDone := func(api string) bool {
		doneMu.Lock()
		defer doneMu.Unlock()
		return isAPIDone[api]
	}

	markDone := func(api string) {
		doneMu.Lock()
		defer doneMu.Unlock()
		isAPIDone[api] = true
	}

	shouldSkip := func(api string) bool {
		return isDone(api)
	}

	wg := &sync.WaitGroup{}
	wg.Add(4)

	go func() {
		defer wg.Done()
		if !shouldSkip("openf1") {
			clients.StreamOpenF1WithLimit(ctx, packetChan, &openf1Count, TargetPerAPI, func() { markDone("openf1") })
		}
	}()

	go func() {
		defer wg.Done()
		if !shouldSkip("finnhub") {
			clients.StreamFinnhubWithLimit(ctx, packetChan, &finnhubCount, TargetPerAPI, func() { markDone("finnhub") })
		}
	}()

	go func() {
		defer wg.Done()
		if !shouldSkip("spacex") {
			clients.StreamSpaceXWithLimit(ctx, packetChan, &spacexCount, TargetPerAPI, func() { markDone("spacex") })
		}
	}()

	go func() {
		defer wg.Done()
		if !shouldSkip("openweather") {
			clients.StreamOpenWeatherWithLimit(ctx, packetChan, &openweatherCount, TargetPerAPI, func() { markDone("openweather") })
		}
	}()

	go func() {
		wg.Wait()
		close(packetChan)
	}()

	file, err := os.Create(fmt.Sprintf("%s/telemetry_%d.json", OutputDir, time.Now().Unix()))
	if err != nil {
		log.Fatal(err)
	}
	defer file.Close()

	absPath, _ := filepath.Abs(file.Name())
	latestPath := fmt.Sprintf("%s/telemetry_latest.json", OutputDir)
	os.Remove(latestPath)
	os.Symlink(absPath, latestPath)

	var packets []clients.Packet
	logTicker := time.NewTicker(ProgressInterval)
	defer logTicker.Stop()

	printCounts := func() {
		log.Printf("Progress: total=%d openf1=%d finnhub=%d spacex=%d openweather=%d",
			len(packets), atomic.LoadInt64(&openf1Count), atomic.LoadInt64(&finnhubCount),
			atomic.LoadInt64(&spacexCount), atomic.LoadInt64(&openweatherCount))
	}

	allAPIDone := func() bool {
		doneMu.Lock()
		defer doneMu.Unlock()
		for _, v := range isAPIDone {
			if !v {
				return false
			}
		}
		return true
	}

	for {
		select {
		case packet, ok := <-packetChan:
			if !ok {
				goto done
			}
			packets = append(packets, packet)
			atomic.AddInt64(&totalPackets, 1)

			if atomic.LoadInt64(&totalPackets) >= TargetPackets || allAPIDone() {
				cancel()
				goto done
			}
		case <-logTicker.C:
			printCounts()
		case <-ctx.Done():
			log.Printf("Timeout or complete: %d packets collected", len(packets))
			goto done
		}
	}
done:

	printCounts()
	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(packets); err != nil {
		log.Fatal(err)
	}

	log.Printf("Ingestion complete: %d packets", len(packets))
}