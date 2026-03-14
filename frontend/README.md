# Resilient RAP Telemetry Dashboard

A real-time telemetry monitoring dashboard built with React, Tailwind CSS, and Recharts.

## Tech Stack
- React 18
- Vite
- Tailwind CSS
- Recharts
- Lucide React (icons)

## Mock WebSocket Server
For development and demonstration purposes, this dashboard includes a simulated WebSocket client (`src/mockServer.js`). It generates realistic telemetry metrics reflecting the Cadillac F1 workload (Sprints vs Weekends) and occasionally simulates system degradation (circuit breaker trips, DLQ spikes).

## To Run
1. Ensure Node.js and npm are installed on your machine.
2. From the `frontend` directory, install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```

## Connecting Real Data
To replace the mock data, update the `useEffect` hook in `src/components/Dashboard.jsx` to connect to your production Kafka consumer / telemetry WebSocket endpoint instead of calling `createMockWebSocket`.