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
	TargetPackets = 10000
	TargetHz      = 100
	OutputDir     = "../../data/ingested"
)

func main() {
	os.MkdirAll(OutputDir, 0755)

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Minute)
	defer cancel()

	var totalPackets int64
	packetChan := make(chan clients.Packet, 10000)

	var wg sync.WaitGroup
	wg.Add(4)

	go func() {
		defer wg.Done()
		clients.StreamOpenF1(ctx, packetChan, &totalPackets)
	}()

	go func() {
		defer wg.Done()
		clients.StreamFinnhub(ctx, packetChan, &totalPackets)
	}()

	go func() {
		defer wg.Done()
		clients.StreamSpaceX(ctx, packetChan, &totalPackets)
	}()

	go func() {
		defer wg.Done()
		clients.StreamOpenMeteo(ctx, packetChan, &totalPackets)
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
	logTicker := time.NewTicker(10 * time.Second)
	defer logTicker.Stop()

	for {
		select {
		case packet, ok := <-packetChan:
			if !ok {
				goto done
			}
			packets = append(packets, packet)
			if atomic.LoadInt64(&totalPackets) >= TargetPackets {
				cancel()
				goto done
			}
		case <-logTicker.C:
			log.Printf("Progress: %d packets collected", len(packets))
		case <-ctx.Done():
			log.Printf("Timeout reached: %d packets collected", len(packets))
			goto done
		}
	}
done:

	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(packets); err != nil {
		log.Fatal(err)
	}

	log.Printf("Ingestion complete: %d packets", len(packets))
}
