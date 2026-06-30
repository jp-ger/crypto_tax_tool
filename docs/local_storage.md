# Local Storage

The application stores normalized transaction data in a local SQLite database.

## Principles

- No private transaction data is sent to cloud services.
- API payloads are normalized before storage.
- Duplicate imports are prevented through a unique `(source, source_id)` key.
- Numeric values are stored as text in the low-level SQLite store to preserve precision before the tax engine processes them as `Decimal`.

## Current tables

### `transactions`

Stores normalized transaction rows.

Important fields:

- `source`: exchange/import source, initially `binance`
- `source_id`: stable external identifier
- `timestamp`: transaction timestamp
- `kind`: trade, convert, reward, deposit, withdrawal, etc.
- `category`: preliminary tax category
- `asset`, `quantity`
- `quote_asset`, `quote_quantity`
- `fee_asset`, `fee_quantity`
- `product`: Binance product family
- `extra_json`: original normalized metadata

### `sync_state`

Stores sync checkpoints such as `last_sync_end`.

## Next improvements

- Add explicit price cache tables.
- Add FIFO lot tables.
- Add audit tables for disposal-to-lot matching.
- Add balance snapshot reconciliation tables.
