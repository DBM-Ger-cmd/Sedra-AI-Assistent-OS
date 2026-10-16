# ADR-001: Use SQLite for the local cache

## Status
Accepted

## Date
2026-10-13

## Context
The tool needs a local cache for lookups. It runs on one machine, needs no server and must start fast.

## Decision
Use SQLite for the local cache.

## Alternatives Considered

### PostgreSQL
- Pros: Strong concurrency
- Cons: Needs a server
- Rejected: Too much setup for a local cache

### JSON files
- Pros: Simple
- Cons: No queries, slow for many entries
- Rejected: Does not scale

## Consequences
- No server to run
- Limited concurrent writes
