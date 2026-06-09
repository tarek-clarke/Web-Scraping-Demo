// Mock WebSocket Server
// Simulates realistic telemetry pipeline metrics

// Simulating high-fidelity workloads:
// Normal Sprint workload: ~86.61% acceptance, 0.228ms p95, 6/6 SLOs
// Normal Weekend workload: ~70.77% acceptance, 0.252ms p95, 3.6M packets, 6/6 SLOs

export function createMockWebSocket(onMessage, onStatusChange) {
  let intervalId = null;
  let isConnected = true;

  // Base state
  let state = {
    throughput: 15600, // packets/sec
    p95Latency: 0.252, // ms
    acceptanceRate: 70.77,
    corruptionRate: 100, // % detected
    uptime: 99.99,
    
    // Circuit Breakers
    circuitBreakers: [
      { id: 'telemetry_fw', label: 'Front Wing', status: 'CLOSED', tripCount: 0, lastTrip: null, recoveryTime: 0 },
      { id: 'telemetry_pu', label: 'Power Unit', status: 'CLOSED', tripCount: 0, lastTrip: null, recoveryTime: 0 },
      { id: 'suspension', label: 'Suspension', status: 'CLOSED', tripCount: 0, lastTrip: null, recoveryTime: 0 },
      { id: 'tires', label: 'Tire Temps', status: 'CLOSED', tripCount: 0, lastTrip: null, recoveryTime: 0 },
    ],

    // DLQ
    dlqStats: {
      depth: 1420,
      schema_drift: 0.1,    // % rate
      duplicate_timestamp: 0.4,
      string_in_numeric: 0.2,
      recoveryRates: { schema_drift: 0, duplicate_timestamp: 100, string_in_numeric: 100 }
    },
    
    // Audit Trail
    auditTrail: [
      { id: 1, hash: 'a1b2c3d4...', valid: true, time: Date.now() },
      { id: 2, hash: 'e5f6g7h8...', valid: true, time: Date.now() - 500 },
      { id: 3, hash: 'i9j0k1l2...', valid: true, time: Date.now() - 1000 },
    ],
    totalSigned: 3600000,
    chainIntact: true,

    // Slo Compliance
    slos: [
      { id: 'latency', name: 'p95 Latency', value: 0.252, target: 0.3, unit: 'ms', status: 'PASS' },
      { id: 'throughput', name: 'Throughput', value: 15600, target: 10000, unit: 'p/s', status: 'PASS' },
      { id: 'uptime', name: 'Uptime', value: 99.99, target: 99.9, unit: '%', status: 'PASS' },
      { id: 'dlq_recovery', name: 'DLQ Recovery Time', value: 45, target: 60, unit: 's', status: 'PASS' },
      { id: 'corruption_detection', name: 'Corruption Detect', value: 100, target: 100, unit: '%', status: 'PASS' },
      { id: 'data_freshness', name: 'Data Freshness', value: 1.2, target: 2.0, unit: 's', status: 'PASS' },
    ]
  };

  const generateTick = () => {
    // Randomize normal fluctuations
    const variance = (Math.random() - 0.5);
    state.throughput = Math.max(10000, Math.min(20000, state.throughput + (variance * 1000)));
    state.p95Latency = Math.max(0.1, Math.min(0.5, state.p95Latency + (variance * 0.05)));
    state.acceptanceRate = Math.max(50, Math.min(100, state.acceptanceRate + (variance * 5)));
    
    // Simulating intermittent spike / breaker trip
    if (Math.random() < 0.05) {
      if (state.circuitBreakers[1].status === 'CLOSED') {
        state.circuitBreakers[1].status = 'OPEN';
        state.circuitBreakers[1].tripCount++;
        state.circuitBreakers[1].lastTrip = new Date().toISOString();
        state.circuitBreakers[1].recoveryTime = 10; // seconds
      }
    }

    // Circuit Breaker auto-recovery countdown
    state.circuitBreakers = state.circuitBreakers.map(cb => {
      if (cb.status === 'OPEN') {
        cb.recoveryTime -= 0.5;
        if (cb.recoveryTime <= 0) cb.status = 'HALF-OPEN';
      } else if (cb.status === 'HALF-OPEN') {
         if (Math.random() > 0.5) {
           cb.status = 'CLOSED';
         } else {
           cb.status = 'OPEN';
           cb.recoveryTime = 5;
           cb.tripCount++;
         }
      }
      return cb;
    });

    // Generate Audit Trail
    state.totalSigned += Math.floor(state.throughput / 2);
    state.auditTrail.unshift({
      id: Math.random(),
      hash: Math.random().toString(36).substring(2, 10) + '...',
      valid: true,
      time: Date.now()
    });
    if (state.auditTrail.length > 10) state.auditTrail.pop();

    // Update SLOs
    state.slos[0].value = state.p95Latency;
    state.slos[0].status = state.p95Latency < 0.3 ? 'PASS' : 'FAIL';
    state.slos[1].value = state.throughput;
    
    // DLQ Depth
    state.dlqStats.depth += Math.floor(variance * 100);
    if (state.dlqStats.depth < 0) state.dlqStats.depth = 10;

    // Dispatch
    onMessage({ ...state, time: Date.now() });
  };

  const connect = () => {
    isConnected = true;
    onStatusChange('CONNECTED');
    intervalId = setInterval(generateTick, 500);
  };

  const disconnect = () => {
    isConnected = false;
    onStatusChange('DISCONNECTED');
    clearInterval(intervalId);
  };

  // simulate initial connection
  setTimeout(connect, 500);

  // simulate random drops occasionally
  setInterval(() => {
    if (Math.random() < 0.02 && isConnected) {
      disconnect();
      setTimeout(connect, 3000);
    }
  }, 10000);

  return {
    disconnect,
    forceGenerate: generateTick
  };
}