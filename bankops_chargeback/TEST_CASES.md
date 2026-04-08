# BankOps Chargeback Test Cases

This document gives a manual and regression-oriented test plan for the full benchmark task set.

## Prerequisites

1. Start the server:

```bash
cd ./ai-hackathon
source .venv/bin/activate
cd bankops_chargeback
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

2. In another terminal, activate the same virtualenv:

```bash
cd ./ai-hackathon
source .venv/bin/activate
```

## Expected Pass Criteria

- `done=True` at the end of the workflow
- `grader.success=True`
- `grader.score == 1.0` for the ideal path
- final message: `Case closed correctly. The dispute was routed and resolved according to policy.`

## Easy Case

- Task id: `easy_unauthorized_card_not_present`
- Goal: identify unauthorized card-not-present fraud and issue provisional credit

### Key evidence

- card is still in customer possession
- recent cross-border ecommerce charge
- no travel notice
- policy says route to Card Disputes with High priority

### Expected analyst decisions

- `dispute_type=card_not_present_fraud`
- `priority=high`
- `assigned_team=card_disputes`
- `resolution=approve_provisional_credit`

### Ideal action sequence

1. `view_transaction`
2. `view_policy`
3. `set_dispute_type(card_not_present_fraud)`
4. `set_priority(high)`
5. `assign_team(card_disputes)`
6. `set_resolution(approve_provisional_credit)`
7. `close_case`

## Medium Case: Subscription Confusion

- Task id: `medium_subscription_confusion`
- Goal: avoid misclassifying a recurring subscription dispute as fraud

### Key evidence

- same recurring merchant and amount for 11 months
- recent legitimate STREAMIFY usage from usual home IP
- policy says this is a merchant billing dispute

### Expected analyst decisions

- `dispute_type=merchant_billing_dispute`
- `priority=medium`
- `assigned_team=billing_disputes`
- `resolution=request_merchant_contact`

### Ideal action sequence

1. `view_transaction`
2. `view_recent_activity`
3. `view_policy`
4. `set_dispute_type(merchant_billing_dispute)`
5. `set_priority(medium)`
6. `assign_team(billing_disputes)`
7. `set_resolution(request_merchant_contact)`
8. `close_case`

## Medium Case: Duplicate Processing Error

- Task id: `medium_duplicate_processing_error`
- Goal: identify a duplicate merchant processing issue rather than fraud

### Key evidence

- two same-day charges for the same merchant and amount
- shared authorization details indicate duplicate processing
- policy says this is a merchant processing error

### Expected analyst decisions

- `dispute_type=merchant_processing_error`
- `priority=medium`
- `assigned_team=billing_disputes`
- `resolution=request_merchant_contact`

### Ideal action sequence

1. `view_transaction`
2. `view_customer_profile`
3. `view_policy`
4. `set_dispute_type(merchant_processing_error)`
5. `set_priority(medium)`
6. `assign_team(billing_disputes)`
7. `set_resolution(request_merchant_contact)`
8. `close_case`

## Hard Case: Wallet Account Takeover

- Task id: `hard_wallet_account_takeover`
- Goal: escalate a digital-wallet account takeover case to fraud operations urgently

### Key evidence

- new wallet provisioning
- password reset from a new browser
- failed one-time-passcode attempts
- rapid high-value tokenized spend
- policy says escalate immediately to Fraud Ops and mark Urgent

### Expected analyst decisions

- `dispute_type=account_takeover`
- `priority=urgent`
- `assigned_team=fraud_ops`
- `resolution=escalate_fraud_investigation`

### Ideal action sequence

1. `view_customer_profile`
2. `view_transaction`
3. `view_recent_activity`
4. `view_policy`
5. `set_dispute_type(account_takeover)`
6. `set_priority(urgent)`
7. `assign_team(fraud_ops)`
8. `set_resolution(escalate_fraud_investigation)`
9. `close_case`

## Hard Case: Friendly Fraud Denial

- Task id: `hard_friendly_fraud_denial`
- Goal: deny a false fraud framing when customer-owned activity is strongly supported

### Key evidence

- device and browsing history tie the purchase to the customer
- fulfillment details support legitimate delivery
- policy says this is not unauthorized fraud

### Expected analyst decisions

- `dispute_type=merchant_billing_dispute`
- `priority=low`
- `assigned_team=billing_disputes`
- `resolution=deny_claim`

### Ideal action sequence

1. `view_customer_profile`
2. `view_transaction`
3. `view_recent_activity`
4. `view_policy`
5. `set_dispute_type(merchant_billing_dispute)`
6. `set_priority(low)`
7. `assign_team(billing_disputes)`
8. `set_resolution(deny_claim)`
9. `close_case`

## Expert Case: Mixed Signals Tight Budget

- Task id: `expert_mixed_signals_tight_budget`
- Goal: identify account takeover under an exact 8-step action budget

### Key evidence

- legitimate travel activity coexists with a suspicious wallet token
- new device provisioning conflicts with otherwise plausible purchases
- policy still requires urgent fraud escalation

### Expected analyst decisions

- `dispute_type=account_takeover`
- `priority=urgent`
- `assigned_team=fraud_ops`
- `resolution=escalate_fraud_investigation`

### Ideal action sequence

1. `view_customer_profile`
2. `view_transaction`
3. `view_recent_activity`
4. `view_policy`
5. `set_dispute_type(account_takeover)`
6. `set_priority(urgent)`
7. `assign_team(fraud_ops)`
8. `set_resolution(escalate_fraud_investigation)`

Expected completion note:

- the case auto-closes after the eighth step because the task budget is exhausted
- a wasted step prevents a perfect outcome

## Quick Regression Command

You can run the automated regression suite with:

```bash
cd ./ai-hackathon
source .venv/bin/activate
python -m unittest discover -s bankops_chargeback/tests -p 'test_*.py' -v
```