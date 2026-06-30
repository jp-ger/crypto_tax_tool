# Binance Sync Scope

This document defines the first supported Binance products and how they are mapped into the internal transaction model.

## Product coverage in the first sync milestone

| Binance product | Endpoint family | Internal kind | Notes |
|---|---|---|---|
| Spot trades | `/api/v3/myTrades` | `trade` | Requires scanning symbols. Daily windows avoid Binance time-window limits. |
| Convert | `/sapi/v1/convert/tradeFlow` | `convert` | Represented as sell leg and buy leg. |
| Asset dividends / rewards | `/sapi/v1/asset/assetDividend` | `reward` | Treated as income-like inflow until reviewed. |
| Simple Earn Flexible rewards | `/sapi/v1/simple-earn/flexible/history/rewardsRecord` | `reward` | Income-like inflow. |
| Simple Earn Locked rewards | `/sapi/v1/simple-earn/locked/history/rewardsRecord` | `reward` | Income-like inflow. |
| Deposits | `/sapi/v1/capital/deposit/hisrec` | `deposit` | Non-taxable transfer by default, but used for inventory plausibility. |
| Withdrawals | `/sapi/v1/capital/withdraw/history` | `withdrawal` | Non-taxable transfer by default, withdrawal fees are recorded. |

## Still to add

- Staking-specific record variants
- Launchpool / Megadrop
- Alpha products if Binance exposes suitable API records
- Fiat deposits and withdrawals
- Wallet snapshots for balance reconciliation
- Pagination beyond the first page for endpoints using `current` / `size`
- API retry and backoff handling

## Design rule

Binance-specific fields are normalized at the API boundary. The tax engine must only use `NormalizedTransaction` records and must not depend on Binance payload structures.
