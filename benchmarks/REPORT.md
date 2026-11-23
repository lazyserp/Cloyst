# Cloyst Performance Benchmark Report

- **Date**: 2026-11-23T13:22:21Z
- **Total Requests Evaluated**: 100
- **Concurrency**: 20
- **Gateway Overhead (Avg Latency)**: 3.164 ms
- **Throughput**: 315.97 requests/sec
- **Cache Hit Latency**: 3.337 ms (100.58x speedup)
- **Offline Embeddings Throughput**: 263.51 req/s

### Measured Latency Percentiles
| Metric | Latency (ms) |
|---|---|
| Average | 3.164 ms |
| P50 | 3.058 ms |
| P95 | 3.724 ms |
| P99 | 6.594 ms |
| Min | 2.744 ms |
| Max | 6.594 ms |

### Comparison to LiteLLM Proxy
| Metric | Cloyst | LiteLLM Proxy |
|---|---|---|
| Gateway Added Latency | 3.164 ms | 2.5 - 5.0 ms |
| Air-Gap Compliance | 100% Guaranteed | Requires custom flags |
| Hot Path DB Calls | 0 (In-Memory Key/State) | 1-2 per request |
| Hash-Chained Audit Logs | Cryptographically Verified | Mutable DB Rows |
