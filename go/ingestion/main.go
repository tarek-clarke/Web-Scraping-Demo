package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"resilient-rap/ingestion/clients"
	"sync"
	"sync/atomic"
	"time"
)

const (
	TargetPackets = 100000
	TargetHz      = 100
	OutputDir     = "../../data/ingested"
)

func main() {
	os.MkdirAll(OutputDir, 0755)

	ctx, cancel := context.WithCancel(context.Background())
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

	latestPath := fmt.Sprintf("%s/telemetry_latest.json", OutputDir)
	os.Remove(latestPath)
	os.Symlink(file.Name(), latestPath)

	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")

	file.WriteString("[\n")
	first := true

	for packet := range packetChan {
		if atomic.LoadInt64(&totalPackets) >= TargetPackets {
			cancel()
			break
		}

		if !first {
			file.WriteString(",\n")
		}
		encoder.Encode(packet)
		first = false
	}

	file.WriteString("\n]")

	log.Printf("Ingestion complete: %d packets", atomic.LoadInt64(&totalPackets))
}
