# Labour Pay — Phase 3: KYC & Funding Infrastructure

Phase 3 extends Phase 1/2 with a KYC gate and bank-transfer funding infrastructure.

## Included
- BVN/NIN KYC provider abstraction.
- Mock KYC provider for development/testing.
- Flutterwave payment-provider adapter.
- Provider customer mapping.
- Static NGN virtual-account architecture.
- Idempotent provider requests.
- Flutterwave webhook signature verification and duplicate protection.
- Payment transaction and webhook event storage.
- No raw BVN/NIN stored in the database; only a one-way identifier hash and verification result/reference are stored.
- Dedicated-account creation is blocked unless the supplied identifier matches a verified KYC record.
- PostgreSQL migrations `0005_kyc` and `0006_payments`.
- Labour Pay official logo retained.

## Important boundary
Phase 3 deliberately does **not** credit a spendable wallet balance from a webhook. Phase 4 introduces the immutable wallet ledger and authoritative financial posting. Until then, webhooks are authenticated, deduplicated, recorded, and acknowledged, but they do not create spendable funds.

## Development mode
```text
PAYMENT_PROVIDER=mock
KYC_PROVIDER=mock
```

## Flutterwave sandbox/staging mode
```text
PAYMENT_PROVIDER=flutterwave
FLW_SECRET_KEY=...
FLW_SECRET_HASH=...
FLW_API_BASE=https://developersandbox-api.flutterwave.com
```

Never commit live or sandbox secrets.

## Migrations
```bash
cd backend
alembic upgrade head
```

## API
- `POST /api/v1/kyc/verify`
- `POST /api/v1/payments/virtual-account`
- `POST /api/v1/webhooks/flutterwave`

Authenticated endpoints use the Phase 2 bearer token.


## Phase 4 — Wallet & Immutable Ledger

Phase 4 adds the financial ledger boundary. Wallet balances are **derived from immutable ledger entries**; there is no mutable `wallet.balance` field. All money is stored as integer kobo in the ledger.

### Included
- User wallet + liability ledger account.
- Double-entry journal transactions and immutable debit/credit entries.
- Server-side balance calculation.
- PostgreSQL row locking for wallet operations.
- Idempotent funding, debit and refund primitives.
- Flutterwave webhook -> server-side charge verification -> wallet credit.
- Funding min/max, daily/monthly and maximum wallet-balance limits stored in DB.
- Wallet transaction history and balance APIs.
- Sanitized webhook persistence; raw originator/payment details are not stored by the Phase 4 webhook handler.
- Development Mock Payment Provider remains available and is never treated as real money.

### Important financial boundary
A Flutterwave webhook is **not** trusted for wallet crediting by itself. Labour Pay re-queries the provider and checks terminal success, NGN currency, amount, reference, and customer ownership before posting the ledger credit. Flutterwave's current documentation also recommends server-side verification before giving value.

### Phase 4 API
- `GET /api/v1/wallet` — authenticated wallet balance/status.
- `GET /api/v1/wallet/transactions` — authenticated transaction history.
- `POST /api/v1/webhooks/flutterwave` — provider webhook endpoint.

### Development commands
```bash
cd /workspaces/Labor-Pay/backend
pip install -r requirements.txt
alembic upgrade head
pytest -q
```

The test suite expects the backend dependencies and PostgreSQL environment to be installed/running. Static validation also checks the ledger and migration source.

Phase 5 should consume `debit_wallet()` for VTU purchases rather than implementing its own balance mutation.
