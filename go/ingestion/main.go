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

	absPath, _ := filepath.Abs(file.Name())
	latestPath := fmt.Sprintf("%s/telemetry_latest.json", OutputDir)
	os.Remove(latestPath)
	os.Symlink(absPath, latestPath)

	var packets []clients.Packet

	for packet := range packetChan {
		if atomic.LoadInt64(&totalPackets) >= TargetPackets {
			cancel()
			break
		}
		packets = append(packets, packet)
	}

	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(packets); err != nil {
		log.Fatal(err)
	}

	log.Printf("Ingestion complete: %d packets", len(packets))
}
