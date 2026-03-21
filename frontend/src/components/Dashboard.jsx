import React, { useState, useEffect } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area, ReferenceLine
} from 'recharts';
import { 
  Activity, AlertTriangle, CheckCircle, Database, Shield, Zap, RefreshCcw, Server
} from 'lucide-react';
import { createMockWebSocket } from '../mockServer';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('CONNECTING');
  const [history, setHistory] = useState([]);
  const [dlqHistory, setDlqHistory] = useState([]);
  const [sessionTime, setSessionTime] = useState(0);

  // Connect to the mock WebSocket (Replace with a real WebSocket later)
  useEffect(() => {
    let ws;
    const connectToDataStr = () => {
      ws = createMockWebSocket(
        (newData) => {
          setData(newData);
          setHistory(prev => {
            const h = [...prev, { time: newData.time, throughput: newData.throughput, latency: newData.p95Latency }];
            if (h.length > 120) h.shift(); // keep 60 seconds (at 2 ticks/sec)
            return h;
          });
          setDlqHistory(prev => {
            const d = [...prev, { time: newData.time, depth: newData.dlqStats.depth }];
            if (d.length > 120) d.shift();
            return d;
          });
        },
        (newStatus) => setStatus(newStatus)
      );
    };

    connectToDataStr();

    // Session Timer
    const timer = setInterval(() => {
        setSessionTime(prev => prev + 1);
    }, 1000);

    return () => {
      if (ws) ws.disconnect();
      clearInterval(timer);
    };
  }, []);

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const getSystemStatus = () => {
      if (status === 'DISCONNECTED') return { text: 'CRITICAL', color: 'text-red-500' };
      if (!data) return { text: 'CONNECTING', color: 'text-yellow-500' };
      
      const failingSLOs = data.slos.filter(slo => slo.status === 'FAIL').length;
      if (failingSLOs > 3) return { text: 'CRITICAL', color: 'text-red-500' };
      if (failingSLOs > 0) return { text: 'DEGRADED', color: 'text-yellow-500' };
      
      return { text: 'RACE-READY', color: 'text-green-500' };
  };

  const sysStat = getSystemStatus();

  return (
    <div className="min-h-screen bg-darkBg text-white p-4 font-sans">
      {/* Top Bar */}
      <header className="flex justify-between items-center mb-6 bg-darkCard p-4 rounded-xl shadow-lg border border-slate-700">
        <div className="flex items-center space-x-4">
          <div className="bg-accentGold text-darkBg px-3 py-1 font-bold rounded">TELEMETRY VALIDATION</div>
          <div className="font-semibold text-lg text-accentSilver">SESSION_01</div>
          <div className="text-xl font-mono text-slate-300 ml-4">{formatTime(sessionTime)}</div>
        </div>
        
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-2">
            <span className="text-sm text-slate-400">WS Connection:</span>
            <span className={`px-2 py-1 rounded text-xs font-bold ${status === 'CONNECTED' ? 'bg-green-900 text-green-400' : 'bg-red-900 text-red-400'}`}>
              {status}
            </span>
          </div>
          <div className="text-right">
             <div className="text-sm text-slate-400">System Status</div>
             <div className={`text-2xl font-bold ${sysStat.color}`}>{sysStat.text}</div>
          </div>
        </div>
      </header>

      {/* Primary Metrics Row */}
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-darkCard p-4 rounded-xl shadow border border-slate-700">
                <div className="flex justify-between items-center mb-2">
                    <h3 className="text-slate-400 font-semibold">Ingestion Throughput</h3>
                    <Zap className="text-blue-400" size={20} />
                </div>
                <div className="text-3xl font-bold mb-4">{Math.round(data.throughput).toLocaleString()}<span className="text-sm font-normal text-slate-500 ml-1">p/s</span></div>
                <div className="h-16">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={history}>
                            <Line type="monotone" dataKey="throughput" stroke="#3b82f6" dot={false} strokeWidth={2} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>

            <div className="bg-darkCard p-4 rounded-xl shadow border border-slate-700">
                <div className="flex justify-between items-center mb-2">
                    <h3 className="text-slate-400 font-semibold">P95 Latency</h3>
                    <Activity className={`${data.p95Latency > 0.3 ? 'text-red-400' : 'text-green-400'}`} size={20} />
                </div>
                <div className={`text-3xl font-bold mb-4 ${data.p95Latency > 0.3 ? 'text-red-400' : 'text-green-400'}`}>
                    {data.p95Latency.toFixed(3)}<span className="text-sm font-normal text-slate-500 ml-1">ms</span>
                </div>
                <div className="h-16">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={history}>
                            <ReferenceLine y={0.3} stroke="#ef4444" strokeDasharray="3 3" />
                            <Line type="monotone" dataKey="latency" stroke="#10b981" dot={false} strokeWidth={2} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>

            <div className="bg-darkCard p-4 rounded-xl shadow border border-slate-700">
                <div className="flex justify-between items-center mb-2">
                    <h3 className="text-slate-400 font-semibold">Acceptance Rate</h3>
                    <CheckCircle className={`${data.acceptanceRate > 80 ? 'text-green-400' : data.acceptanceRate > 60 ? 'text-yellow-400' : 'text-red-400'}`} size={20} />
                </div>
                <div className="text-4xl font-bold mt-4">
                    <span className={`${data.acceptanceRate > 80 ? 'text-green-400' : data.acceptanceRate > 60 ? 'text-yellow-400' : 'text-red-400'}`}>
                        {data.acceptanceRate.toFixed(2)}%
                    </span>
                </div>
            </div>

            <div className="bg-darkCard p-4 rounded-xl shadow border border-slate-700">
                <div className="flex justify-between items-center mb-2">
                    <h3 className="text-slate-400 font-semibold">Corruption Detection</h3>
                    <Shield className="text-purple-400" size={20} />
                </div>
                <div className="text-4xl font-bold mt-4 text-purple-400">{data.corruptionRate}%</div>
                <div className="text-sm text-slate-400 mt-2">Target: 100%</div>
            </div>
        </div>
      )}

      {/* Main Grid: Breakers, DLQ, Audit, SLOs, GDPR */}
      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Left Column */}
            <div className="space-y-6">
                {/* Circuit Breakers Panel */}
                <div className="bg-darkCard p-4 rounded-xl shadow border border-slate-700">
                    <h3 className="text-lg font-bold text-slate-300 border-b border-slate-700 pb-2 mb-4 flex items-center">
                        <Server className="mr-2" size={20} /> Circuit Breakers
                    </h3>
                    <div className="space-y-3">
                        {data.circuitBreakers.map(cb => (
                            <div key={cb.id} className="flex justify-between items-center bg-slate-800/50 p-3 rounded">
                                <div>
                                    <div className="font-semibold">{cb.label}</div>
                                    <div className="text-xs text-slate-400">Trips: {cb.tripCount}</div>
                                </div>
                                <div className="text-right">
                                    <span className={`px-2 py-1 rounded text-xs font-bold ${cb.status === 'CLOSED' ? 'bg-green-900 text-green-400' : cb.status === 'OPEN' ? 'bg-red-900 text-red-400' : 'bg-yellow-900 text-yellow-400'}`}>
                                        {cb.status}
                                    </span>
                                    {cb.status !== 'CLOSED' && (
                                        <div className="text-xs text-slate-400 mt-1">Recover in: {cb.recoveryTime}s</div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* GDPR / Data Sovereignty */}
                <div className="bg-darkCard p-4 rounded-xl shadow border border-slate-700">
                    <h3 className="text-lg font-bold text-slate-300 border-b border-slate-700 pb-2 mb-4">Data Sovereignty</h3>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <div className="text-sm text-slate-400">Current Zone</div>
                            <div className="font-bold text-blue-400">US-West (Nevada)</div>
                        </div>
                        <div>
                            <div className="text-sm text-slate-400">Compliance Regime</div>
                            <div className="font-bold text-amber-500">Non-GDPR</div>
                        </div>
                        <div className="col-span-2">
                            <div className="text-sm text-slate-400 mb-1">Routing Indicator</div>
                            <div className="w-full bg-slate-700 rounded-full h-2.5">
                                 <div className="bg-blue-500 h-2.5 rounded-full" style={{ width: '100%' }}></div>
                            </div>
                            <div className="text-xs text-slate-500 mt-1">Local Edge Persistence → US Core Cloud</div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Middle Column */}
            <div className="space-y-6">
                {/* DLQ Panel */}
                <div className="bg-darkCard p-4 rounded-xl shadow border border-slate-700">
                    <div className="flex justify-between items-center border-b border-slate-700 pb-2 mb-4">
                        <h3 className="text-lg font-bold text-slate-300 flex items-center">
                            <Database className="mr-2" size={20} /> Dead Letter Queue
                        </h3>
                        <span className="bg-red-900/50 text-red-400 px-2 py-1 rounded text-sm font-bold">
                            Depth: {data.dlqStats.depth}
                        </span>
                    </div>

                    <div className="h-32 mb-4">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={dlqHistory}>
                                <Area type="monotone" dataKey="depth" stroke="#f43f5e" fill="#9f1239" opacity={0.3} />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>

                    <div className="space-y-2 mb-4">
                        <div className="flex justify-between text-sm">
                            <span className="text-slate-400">schema_drift</span>
                            <span className="text-red-400 font-mono">0% recovered</span>
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-slate-400">duplicate_timestamp</span>
                            <span className="text-green-400 font-mono">100% recovered</span>
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-slate-400">string_in_numeric</span>
                            <span className="text-green-400 font-mono">100% recovered</span>
                        </div>
                    </div>
                    
                    <button className="w-full bg-slate-700 hover:bg-slate-600 transition p-2 rounded text-sm text-center text-slate-300">
                        Inspect Recent Entries
                    </button>
                </div>

                {/* Audit Trail */}
                <div className="bg-darkCard p-4 rounded-xl shadow border border-slate-700">
                     <div className="flex justify-between items-center border-b border-slate-700 pb-2 mb-4">
                        <h3 className="text-lg font-bold text-slate-300 flex items-center">
                            <Shield className="mr-2" size={20} /> Audit Trail
                        </h3>
                        {data.chainIntact ? 
                           ( <span className="flex items-center text-green-400 text-sm"><CheckCircle size={14} className="mr-1"/> INTACT</span> ) :
                           ( <span className="flex items-center text-red-400 text-sm"><AlertTriangle size={14} className="mr-1"/> BROKEN</span> )
                        }
                    </div>
                    <div className="text-sm text-slate-400 mb-3">Total Signed: {data.totalSigned.toLocaleString()}</div>
                    <div className="space-y-2 h-40 overflow-hidden relative">
                         <div className="absolute inset-0 bg-gradient-to-b from-transparent to-darkCard pointer-events-none"></div>
                         {data.auditTrail.map((entry, idx) => (
                             <div key={idx} className="flex justify-between items-center text-xs font-mono bg-slate-800/50 p-2 rounded opacity-80">
                                <span className="text-slate-500">{new Date(entry.time).toISOString().split('T')[1].replace('Z','')}</span>
                                <span className="text-slate-300">sha256:{entry.hash}</span>
                                <span className="text-green-400">VALID</span>
                             </div>
                         ))}
                    </div>
                </div>
            </div>

            {/* Right Column */}
            <div className="space-y-6">
                 {/* SLO Compliance */}
                 <div className="bg-darkCard p-4 rounded-xl shadow border border-slate-700 h-full">
                    <h3 className="text-lg font-bold text-slate-300 border-b border-slate-700 pb-2 mb-4 flex items-center">
                        <Activity className="mr-2" size={20} /> SLO Compliance
                    </h3>
                    
                    <div className="space-y-4">
                        {data.slos.map(slo => (
                            <div key={slo.id} className="bg-slate-800/30 p-3 rounded border border-slate-700/50">
                                <div className="flex justify-between items-center mb-1">
                                    <span className="text-sm font-semibold text-slate-300">{slo.name}</span>
                                    <span className={`text-xs px-2 py-0.5 rounded font-bold ${slo.status === 'PASS' ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                                        {slo.status}
                                    </span>
                                </div>
                                <div className="flex justify-between items-end">
                                    <div className="text-lg font-mono">
                                        <span className={slo.status === 'PASS' ? 'text-slate-100' : 'text-red-400'}>
                                            {typeof slo.value === 'number' ? slo.value.toFixed(slo.value < 1 ? 3 : 1) : slo.value}
                                        </span>
                                        <span className="text-xs text-slate-500 ml-1">{slo.unit}</span>
                                    </div>
                                    <div className="text-xs text-slate-500">
                                        Target: {slo.status === 'PASS' ? '<' : '>'} {slo.target}{slo.unit}
                                    </div>
                                </div>
                                {/* Progress Bar Indicator */}
                                <div className="w-full bg-slate-700/50 rounded-full h-1 mt-2 overflow-hidden">
                                     <div className={`h-1 rounded-full ${slo.status === 'PASS' ? 'bg-green-500' : 'bg-red-500'}`} style={{ width: `${Math.min(100, (slo.value/slo.target)*100)}%` }}></div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

        </div>
      )}

      {/* Disconnected Overlay */}
      {status === 'DISCONNECTED' && (
          <div className="fixed inset-0 bg-darkBg/80 backdrop-blur-sm flex flex-col items-center justify-center z-50">
              <AlertTriangle size={64} className="text-red-500 mb-4" />
              <h2 className="text-3xl font-bold text-white mb-2">CONNECTION LOST</h2>
              <p className="text-slate-400 mb-6">Attempting to reconnect to telemetry stream...</p>
              <RefreshCcw className="text-slate-500 animate-spin" size={32} />
          </div>
      )}
    </div>
  );
}