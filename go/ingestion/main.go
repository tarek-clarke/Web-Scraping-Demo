package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"resilient-rap/ingestion/clients"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

const (
	OutputDir        = "../../data/ingested"
	ProgressInterval = 10 * time.Second
)

func main() {
	os.MkdirAll(OutputDir, 0755)

	// Ingest until stopped or session ends (timeout at 2h to match SLURM decoder)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Hour)
	defer cancel()

	// Channel to handle graceful interrupts (Ctrl+C, SIGTERM from SLURM epilog)
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	go func() {
		select {
		case <-sigChan:
			log.Println("Interrupt received, stopping ingestion gracefully...")
			cancel()
		case <-ctx.Done():
		}
	}()

	packetChan := make(chan clients.Packet, 100000)

	var (
		totalPackets     int64
		openf1Count      int64
		finnhubCount     int64
		spacexCount      int64
		openweatherCount int64
	)

	isAPIDone := map[string]bool{
		"openf1":      false,
		"finnhub":     false,
		"spacex":      false,
		"openweather": false,
	}

	var doneMu sync.Mutex

	markDone := func(api string) {
		doneMu.Lock()
		defer doneMu.Unlock()
		isAPIDone[api] = true
	}

	isDone := func(api string) bool {
		doneMu.Lock()
		defer doneMu.Unlock()
		return isAPIDone[api]
	}

	// If no keys are provided, mark APIs done immediately to skip network waits
	if os.Getenv("FINNHUB_API_KEY") == "" {
		log.Println("Finnhub: no API key provided, marking done immediately")
		markDone("finnhub")
	}
	if os.Getenv("OPENWEATHER_API_KEY") == "" {
		log.Println("OpenWeather: no API key provided, marking done immediately")
		markDone("openweather")
	}
	if os.Getenv("SKIP_SPACEX") == "true" {
		log.Println("SpaceX: SKIP_SPACEX set, marking done immediately")
		markDone("spacex")
	}

	wg := &sync.WaitGroup{}
	wg.Add(4)

	go func() {
		defer wg.Done()
		if !isDone("openf1") {
			clients.StreamOpenF1(ctx, packetChan, &openf1Count)
		}
		markDone("openf1")
	}()

	go func() {
		defer wg.Done()
		if !isDone("finnhub") {
			clients.StreamFinnhub(ctx, packetChan, &finnhubCount)
		}
		markDone("finnhub")
	}()

	go func() {
		defer wg.Done()
		if !isDone("spacex") {
			clients.StreamSpaceX(ctx, packetChan, &spacexCount)
		}
		markDone("spacex")
	}()

	go func() {
		defer wg.Done()
		if !isDone("openweather") {
			clients.StreamOpenWeather(ctx, packetChan, &openweatherCount)
		}
		markDone("openweather")
	}()

	go func() {
		wg.Wait()
		close(packetChan)
	}()

	// Use human readable date format in the file name
	timestamp := time.Now().Format("20060102_150405")
	filePath := fmt.Sprintf("%s/telemetry_%s.json", OutputDir, timestamp)
	file, err := os.Create(filePath)
	if err != nil {
		log.Fatal(err)
	}
	defer file.Close()

	// Atomic symlink swap: create temp symlink, then rename over target
	absPath, _ := filepath.Abs(file.Name())
	latestPath := fmt.Sprintf("%s/telemetry_latest.json", OutputDir)
	tmpLink := latestPath + ".tmp"
	os.Remove(tmpLink)
	if err := os.Symlink(absPath, tmpLink); err == nil {
		os.Rename(tmpLink, latestPath)
	}

	writer := bufio.NewWriterSize(file, 64*1024) // 64KB write buffer

	printCounts := func() {
		log.Printf("Progress: total=%d openf1=%d finnhub=%d spacex=%d openweather=%d",
			atomic.LoadInt64(&totalPackets), atomic.LoadInt64(&openf1Count), atomic.LoadInt64(&finnhubCount),
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

	logTicker := time.NewTicker(ProgressInterval)
	defer logTicker.Stop()

	flushTicker := time.NewTicker(1 * time.Second)
	defer flushTicker.Stop()

	for {
		select {
		case packet, ok := <-packetChan:
			if !ok {
				goto drain
			}

			// Marshal packet as a single JSON line
			bytes, err := json.Marshal(packet)
			if err == nil {
				writer.Write(bytes)
				writer.WriteByte('\n')
			}

			atomic.AddInt64(&totalPackets, 1)

			// Inline flush check to prevent starvation under high throughput
			select {
			case <-flushTicker.C:
				writer.Flush()
			default:
			}

			if allAPIDone() {
				cancel()
				goto drain
			}
		case <-flushTicker.C:
			writer.Flush()
		case <-logTicker.C:
			printCounts()
		case <-ctx.Done():
			log.Printf("Ingestor stopped: %d packets collected", atomic.LoadInt64(&totalPackets))
			goto drain
		}
	}

drain:
	// Drain any remaining buffered packets before exiting
	for {
		select {
		case packet, ok := <-packetChan:
			if !ok {
				goto done
			}
			bytes, err := json.Marshal(packet)
			if err == nil {
				writer.Write(bytes)
				writer.WriteByte('\n')
			}
			atomic.AddInt64(&totalPackets, 1)
		default:
			goto done
		}
	}

done:
	printCounts()
	writer.Flush()
	file.Sync() // fsync to ensure data reaches Lustre
	log.Printf("Ingestion complete: %d packets saved to %s", atomic.LoadInt64(&totalPackets), filePath)
}