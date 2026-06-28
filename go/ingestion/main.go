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
	"syscall"
	"sync"
	"sync/atomic"
	"time"
)

const (
	OutputDir         = "../../data/ingested"
	ProgressInterval  = 10 * time.Second
)

func main() {
	os.MkdirAll(OutputDir, 0755)

	// Ingest until stopped or session ends (timeout at 3 hours just in case)
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Hour)
	defer cancel()

	// Channel to handle graceful interrupts (Ctrl+C)
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sigChan
		log.Println("Interrupt received, stopping ingestion gracefully...")
		cancel()
	}()

	packetChan := make(chan clients.Packet, 100000)

	var (
		totalPackets     int64
		openf1Count     int64
		finnhubCount     int64
		spacexCount      int64
		openweatherCount int64
	)

	isAPIDone := map[string]bool{
		"openf1":      false,
		"finnhub":      false,
		"spacex":      false,
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

	// If no keys are provided, we mark them done immediately to skip network waits
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
		if !shouldSkip("openf1") {
			clients.StreamOpenF1(ctx, packetChan, &openf1Count)
			markDone("openf1")
		} else {
			markDone("openf1")
		}
	}()

	go func() {
		defer wg.Done()
		if !shouldSkip("finnhub") {
			clients.StreamFinnhub(ctx, packetChan, &finnhubCount)
			markDone("finnhub")
		} else {
			markDone("finnhub")
		}
	}()

	go func() {
		defer wg.Done()
		if !shouldSkip("spacex") {
			clients.StreamSpaceX(ctx, packetChan, &spacexCount)
			markDone("spacex")
		} else {
			markDone("spacex")
		}
	}()

	go func() {
		defer wg.Done()
		if !shouldSkip("openweather") {
			clients.StreamOpenWeather(ctx, packetChan, &openweatherCount)
			markDone("openweather")
		} else {
			markDone("openweather")
		}
	}()

	go func() {
		wg.Wait()
		close(packetChan)
	}()

	// Use human readable date format in the file name
	timestamp := time.Now().Format("20060102_150405")
	file, err := os.Create(fmt.Sprintf("%s/telemetry_%s.json", OutputDir, timestamp))
	if err != nil {
		log.Fatal(err)
	}
	defer file.Close()

	absPath, _ := filepath.Abs(file.Name())
	latestPath := fmt.Sprintf("%s/telemetry_latest.json", OutputDir)
	os.Remove(latestPath)
	os.Symlink(absPath, latestPath)

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

	// Flush buffer periodically to disk (so decoder sees it)
	flushTicker := time.NewTicker(1 * time.Second)
	defer flushTicker.Stop()

	for {
		select {
		case packet, ok := <-packetChan:
			if !ok {
				goto done
			}
			
			// Marshal packet as a single JSON line
			bytes, err := json.Marshal(packet)
			if err == nil {
				writer.Write(bytes)
				writer.WriteByte('\n')
			}
			
			atomic.AddInt64(&totalPackets, 1)

			if allAPIDone() {
				cancel()
				goto done
			}
		case <-flushTicker.C:
			writer.Flush()
		case <-logTicker.C:
			printCounts()
		case <-ctx.Done():
			log.Printf("Injestor stopped: %d packets collected", atomic.LoadInt64(&totalPackets))
			goto done
		}
	}
done:
	printCounts()
	writer.Flush()
	log.Printf("Ingestion complete: %d packets saved to %s", atomic.LoadInt64(&totalPackets), file.Name())
}