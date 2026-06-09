# Resilient RAP Framework — Research Dashboard

**Live observability & domain agnosticism testing for GPU-accelerated telemetry processing.**

📊 **[Open Dashboard](./index.html)** 

## Features

- **Real-Time Metrics**: Circuit breaker state, throughput, DLQ monitoring
- **BERT Reconciliation Visualizer**: See sensor name mappings with confidence scores
- **Domain Agnosticism Testing**: Test APIs against automotive, healthcare, aerospace schemas
- **Performance Benchmarks**: Results from Apple M4, NVIDIA Hopper/Ada/Blackwell, AMD 7900XT
- **Rate Limiting**: Protected against abuse (20 tests/day, 60s cooldown)

## Architecture

```
3-Tier Resilient Reconciliation
├── Tier 1: Verified Cache (O(1) — Previously validated mappings)
├── Tier 2: BERT Semantic Inference (O(n) — GPU-accelerated BERT)
└── Tier 3: Human-in-the-Loop (Expert review for low-confidence)
```

## Quick Start

1. **Open the [Dashboard](./index.html)**
2. **Test Domain Agnosticism**:
   - Set your GitHub token: Click "Set token" and paste a personal access token
   - Enter API endpoint: `https://api.example.com/telemetry`
   - Enter domain name: `automotive` or `healthcare`
   - Click **▶ Test Domain**

3. **View Results**:
   - BERT reconciliation transformations
   - Confidence scores for each mapping
   - Tier classification (Cache vs. BERT vs. Human Review)

## Quick Start

1. **Open the [Dashboard](./index.html)**
2. **Test Domain Agnosticism**:
   - Set your GitHub token: Click "Set token" and paste a personal access token
   - Enter API endpoint: `https://api.example.com/telemetry`
   - Enter domain name: `automotive` or `healthcare`
   - Click **▶ Test Domain**

3. **View Results**:
   - BERT reconciliation transformations
   - Confidence scores for each mapping
   - Tier classification (Cache vs. BERT vs. Human Review)

## Rate Limits

- **60 seconds** between tests (per session)
- **20 tests per 24 hours** (daily quota)
- **GitHub authentication required** (prevents bot abuse)

## Benchmarks

See performance across hardware platforms in [README.md](../README.md#performance--scaling-validation):
- **M4**: 0.004 ms p95 latency
- **Blackwell B200**: 0.008 ms p95 latency  
- **Hopper H200**: 0.006 ms p95 latency
- **7900 XT**: 0.008 ms p95 latency

## GitHub Repository

📦 [resilient-rap-framework](https://github.com/tarek-clarke/resilient-rap-framework)

## Cross-Domain Translations

See the detailed cross-domain translation matrix: [TRANSLATIONS.md](./TRANSLATIONS.md)

## License

PolyForm Non-commercial — See [LICENSE](../LICENSE)
