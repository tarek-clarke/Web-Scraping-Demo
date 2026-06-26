package main

import (
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
			// Stream infinitely (StreamOpenF1 has no limit)
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

	var isWriting int32

	flushPackets := func() {
		if !atomic.CompareAndSwapInt32(&isWriting, 0, 1) {
			log.Println("Previous flush still in progress, skipping this tick")
			return
		}

		// Create a copy of packets to encode asynchronously
		packetsCopy := make([]clients.Packet, len(packets))
		copy(packetsCopy, packets)

		go func(pkts []clients.Packet) {
			defer atomic.StoreInt32(&isWriting, 0)

			tempFile := fmt.Sprintf("%s.tmp", file.Name())
			f, err := os.Create(tempFile)
			if err != nil {
				log.Printf("Error creating temp file: %v", err)
				return
			}

			encoder := json.NewEncoder(f)
			encoder.SetIndent("", "  ")
			if err := encoder.Encode(pkts); err != nil {
				log.Printf("Error encoding packets: %v", err)
				f.Close()
				os.Remove(tempFile)
				return
			}
			f.Close()

			if err := os.Rename(tempFile, file.Name()); err != nil {
				log.Printf("Error renaming temp file: %v", err)
			}
		}(packetsCopy)
	}

	for {
		select {
		case packet, ok := <-packetChan:
			if !ok {
				goto done
			}
			packets = append(packets, packet)
			atomic.AddInt64(&totalPackets, 1)

			if allAPIDone() {
				cancel()
				goto done
			}
		case <-logTicker.C:
			printCounts()
			flushPackets()
		case <-ctx.Done():
			log.Printf("Injestor stopped: %d packets collected", len(packets))
			goto done
		}
	}
done:

	printCounts()
	flushPackets()

	log.Printf("Ingestion complete: %d packets saved to %s", len(packets), file.Name())
}