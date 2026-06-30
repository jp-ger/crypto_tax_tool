# Data model

The application separates exchange-specific API payloads from the internal tax model.

## Normalized transaction

A normalized transaction is the first stable internal representation.

Core fields:

- `source`: exchange/source identifier, initially `binance`
- `source_id`: stable external identifier for de-duplication
- `timestamp`: event time in UTC
- `kind`: trade, convert, reward, income, deposit, withdrawal, fee or adjustment
- `tax_category`: initial tax classification
- `asset` and `quantity`: primary asset movement
- `quote_asset` and `quote_quantity`: counter asset movement for trades/converts
- `fee_asset` and `fee_quantity`: explicit fee movement
- `product`: exchange product, e.g. spot, earn, convert
- `raw_type`: original API source type
- `metadata`: source-specific context for auditability

## Persistence

The first persistence layer uses SQLite directly for robust local storage and simple packaging.
The database contains:

- `transactions`: normalized transaction records
- `sync_state`: simple key-value checkpoints for future delta sync

Next extensions:

- prices
- lots
- disposals
- sync runs
- warnings
