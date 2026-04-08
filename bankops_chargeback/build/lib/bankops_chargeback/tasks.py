"""Deterministic banking chargeback tasks for the OpenEnv environment."""

from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class ChargebackTask:
    """Single deterministic chargeback operations case."""

    task_id: str
    difficulty: str
    title: str
    objective: str
    case_summary: str
    customer_profile: str
    transaction_details: str
    recent_activity: str
    policy_excerpt: str
    expected_dispute_type: str
    expected_priority: str
    expected_team: str
    expected_resolution: str
    required_reviews: Tuple[str, ...]
    max_steps: int = 10


def _clean(text: str) -> str:
    return dedent(text).strip()


TASKS: Dict[str, ChargebackTask] = {
    "easy_unauthorized_card_not_present": ChargebackTask(
        task_id="easy_unauthorized_card_not_present",
        difficulty="easy",
        title="Unauthorized Cross-Border Ecommerce Charge",
        objective=(
            "Review the dispute, identify the correct dispute type, choose the right "
            "priority and team, then select the correct resolution before closing the case."
        ),
        case_summary=_clean(
            """
            Channel: mobile dispute form
            Customer statement: "I still have my debit card with me. I was asleep in Texas
            when a 428.19 USD TECHGADGETS ONLINE transaction posted from Singapore. I did not
            make this purchase."
            Case notes:
            - Reported within 12 hours of the posting time
            - Customer confirms no travel notice was filed
            - Physical card remains active and in the customer's possession
            """
        ),
        customer_profile=_clean(
            """
            - Retail checking and debit card customer since 2018
            - Home location: Austin, Texas
            - Prior disputes in the last 24 months: 0
            - Verified same-day legitimate purchases: grocery store and gas station in Austin
            - No travel notifications or overseas merchant history in the last 90 days
            """
        ),
        transaction_details=_clean(
            """
            - Amount: 428.19 USD
            - Merchant: TECHGADGETS ONLINE
            - Merchant country: Singapore
            - Channel: ecommerce card-not-present
            - First-time merchant on this card: yes
            - Two declined authorization attempts from the same merchant occurred 3 minutes earlier
            """
        ),
        recent_activity=_clean(
            """
            - No online banking password change in the last 30 days
            - No new digital wallet token provisioning events
            - No login anomalies or account recovery events detected
            """
        ),
        policy_excerpt=_clean(
            """
            If the customer still has the card, reports the charge within 60 days, and the
            transaction is clearly unauthorized card-not-present spend, open a fraud chargeback,
            route the case to Card Disputes, and issue provisional credit. Use High priority when
            the transaction is recent and cross-border.
            """
        ),
        expected_dispute_type="card_not_present_fraud",
        expected_priority="high",
        expected_team="card_disputes",
        expected_resolution="approve_provisional_credit",
        required_reviews=("transaction", "policy"),
    ),
    "medium_subscription_confusion": ChargebackTask(
        task_id="medium_subscription_confusion",
        difficulty="medium",
        title="Recurring Subscription Misrecognition",
        objective=(
            "Determine whether the charge is fraud or a billing dispute, route it correctly, "
            "and choose the correct customer-facing resolution."
        ),
        case_summary=_clean(
            """
            Channel: secure message inbox
            Customer statement: "Please reverse the 19.99 USD STREAMIFY PREMIUM charge. I do not
            recognize it and I don't want to pay for it."
            Case notes:
            - Customer reports no card loss and no travel
            - Charge was disputed 5 days after posting
            - No previous fraud freeze was placed on the card
            """
        ),
        customer_profile=_clean(
            """
            - Checking, savings, and rewards credit card customer since 2020
            - Primary email and device fingerprint unchanged for 18 months
            - Merchant communication preference: email only
            - No recent fraud claims on file
            """
        ),
        transaction_details=_clean(
            """
            - Amount: 19.99 USD
            - Merchant: STREAMIFY PREMIUM
            - Merchant category: digital entertainment subscription
            - Same descriptor and amount posted on the 15th of each month for the last 11 months
            - Card token remained active after a plastic reissue 3 months ago
            """
        ),
        recent_activity=_clean(
            """
            - Customer successfully logged in to STREAMIFY from their usual home IP 3 days ago
            - No unusual card authorization velocity or location changes detected
            - Email inbox shows a merchant receipt and annual plan reminder from STREAMIFY
            """
        ),
        policy_excerpt=_clean(
            """
            Recognized recurring billing with consistent prior history is a merchant billing
            dispute, not unauthorized fraud. Do not issue provisional credit. Route to Billing
            Disputes with Medium priority and instruct the customer to contact the merchant or
            cancel the subscription if they no longer want the service.
            """
        ),
        expected_dispute_type="merchant_billing_dispute",
        expected_priority="medium",
        expected_team="billing_disputes",
        expected_resolution="request_merchant_contact",
        required_reviews=("transaction", "recent_activity", "policy"),
    ),
    "hard_wallet_account_takeover": ChargebackTask(
        task_id="hard_wallet_account_takeover",
        difficulty="hard",
        title="Digital Wallet Account Takeover Escalation",
        objective=(
            "Handle a complex wallet dispute with account takeover indicators. Review the case, "
            "identify the risk correctly, and escalate it to the right team with the right urgency."
        ),
        case_summary=_clean(
            """
            Channel: branch-assisted fraud case
            Customer statement: "My phone lost service this morning and now I see two wallet
            purchases I definitely did not make. I still have my physical card in my wallet."
            Case notes:
            - Premier customer with same-day branch callback request
            - Case opened 41 minutes after the second transaction posted
            - Customer reports they were at work in Chicago during the disputed spend
            """
        ),
        customer_profile=_clean(
            """
            - Premier checking and credit customer since 2016
            - Home city: Chicago, Illinois
            - Card remains active and physically present with the customer
            - Telecom note on file: reported sudden mobile service loss earlier today
            - Relationship manager tagged the case as high-visibility
            """
        ),
        transaction_details=_clean(
            """
            - Transaction 1: 1,240.55 USD at METRO ELECTRONICS, tokenized mobile wallet purchase
            - Transaction 2: 684.10 USD at CITY LUXE GOODS, tokenized mobile wallet purchase
            - Both purchases posted in New York within 9 minutes of each other
            - No prior wallet purchases exist for this card in the previous 12 months
            """
        ),
        recent_activity=_clean(
            """
            - Online banking password reset from a new browser 18 minutes before the first purchase
            - Three failed one-time-passcode attempts immediately before a new wallet token was added
            - New payee creation attempt blocked by velocity controls
            - No travel notice or customer-initiated device enrollment recorded
            """
        ),
        policy_excerpt=_clean(
            """
            When a dispute contains account takeover indicators such as credential reset from a new
            device, fresh wallet provisioning, and rapid high-value spend, escalate to Fraud Ops
            immediately. Mark the case Urgent. Do not finalize it as a routine merchant or standard
            card-not-present dispute.
            """
        ),
        expected_dispute_type="account_takeover",
        expected_priority="urgent",
        expected_team="fraud_ops",
        expected_resolution="escalate_fraud_investigation",
        required_reviews=("customer_profile", "transaction", "recent_activity", "policy"),
        max_steps=12,
    ),
    "medium_duplicate_processing_error": ChargebackTask(
        task_id="medium_duplicate_processing_error",
        difficulty="medium",
        title="Duplicate Merchant Charge Investigation",
        objective=(
            "Investigate a pair of identical charges from one merchant. Determine whether "
            "this is fraud or a processing error, then classify, route, and resolve the case."
        ),
        case_summary=_clean(
            """
            Channel: phone call to card services
            Customer statement: "I bought one TV from Riverside Electronics for 549.99 USD
            but I see two charges for 549.99 on my statement from the same day. I only made
            one purchase and only took one TV home."
            Case notes:
            - Customer called 3 days after the posting date
            - Both charges carry the same authorization code
            - Customer has receipt for a single purchase
            """
        ),
        customer_profile=_clean(
            """
            - Checking and debit card customer since 2019
            - Home city: Portland, Oregon
            - Shops at Riverside Electronics approximately once per quarter
            - No prior disputes filed in the last 36 months
            - No fraud alerts or account locks on file
            """
        ),
        transaction_details=_clean(
            """
            - Charge 1: 549.99 USD at RIVERSIDE ELECTRONICS, in-store chip-read, 10:42 AM
            - Charge 2: 549.99 USD at RIVERSIDE ELECTRONICS, in-store chip-read, 10:56 AM
            - Both transactions share authorization code AUT-7829314
            - Merchant terminal ID is identical for both charges
            - No other charges from this merchant in the last 90 days
            """
        ),
        recent_activity=_clean(
            """
            - Normal debit card usage across grocery, fuel, and dining merchants
            - No failed PIN attempts or card-present anomalies
            - No digital wallet activity or online password changes
            - Card has not been reported lost or stolen
            """
        ),
        policy_excerpt=_clean(
            """
            When two charges share the same authorization code and originate from the same
            terminal within a short window, classify the duplicate as a merchant processing
            error, not fraud. Route to Billing Disputes at Medium priority and instruct the
            team to contact the merchant for a correction.
            """
        ),
        expected_dispute_type="merchant_processing_error",
        expected_priority="medium",
        expected_team="billing_disputes",
        expected_resolution="request_merchant_contact",
        required_reviews=("transaction", "customer_profile", "policy"),
    ),
    "hard_friendly_fraud_denial": ChargebackTask(
        task_id="hard_friendly_fraud_denial",
        difficulty="hard",
        title="Friendly Fraud — Customer-Initiated Purchase Denial",
        objective=(
            "Evaluate a customer's fraud claim against strong counter-evidence showing the "
            "customer likely made the purchase. Classify correctly and choose the right "
            "resolution even when it contradicts the customer's statement."
        ),
        case_summary=_clean(
            """
            Channel: online dispute form
            Customer statement: "I did not authorize the 892.00 USD charge from LUXE FASHION
            HOUSE. Someone must have used my card details online. Please reverse this
            immediately."
            Case notes:
            - Disputed 8 days after the transaction posted
            - Customer has not reported the card lost or stolen
            - No fraud freeze on the account
            """
        ),
        customer_profile=_clean(
            """
            - Rewards credit card customer since 2017
            - Home address: 412 Maple Drive, Denver, Colorado 80204
            - Regular online shopper with 15+ ecommerce merchants in the last 6 months
            - One prior dispute 14 months ago was withdrawn by the customer after merchant
              provided proof of delivery
            - Email and phone number unchanged for 2 years
            """
        ),
        transaction_details=_clean(
            """
            - Amount: 892.00 USD
            - Merchant: LUXE FASHION HOUSE (online retailer)
            - Channel: ecommerce card-not-present
            - Shipping address on the order: 412 Maple Drive, Denver, CO 80204
            - Delivery carrier confirms signed delivery at that address 2 days after purchase
            - Device fingerprint matches the customer's primary laptop (seen in 90% of
              their online transactions)
            """
        ),
        recent_activity=_clean(
            """
            - Customer browsed luxefashionhouse.com from their home IP 3 hours before the
              purchase (cookie trail confirms same browser session)
            - Customer logged into their bank app from the same device 10 minutes after
              the purchase
            - No VPN, proxy, or TOR usage detected
            - No password resets or suspicious login attempts
            """
        ),
        policy_excerpt=_clean(
            """
            When delivery was confirmed to the cardholder's address, the device fingerprint
            matches the customer's known device, and browsing history shows pre-purchase
            activity on the merchant site, the dispute does not qualify as unauthorized fraud.
            Classify as a merchant billing dispute, set priority to Low, route to Billing
            Disputes, and deny the chargeback claim.
            """
        ),
        expected_dispute_type="merchant_billing_dispute",
        expected_priority="low",
        expected_team="billing_disputes",
        expected_resolution="deny_claim",
        required_reviews=("customer_profile", "transaction", "recent_activity", "policy"),
        max_steps=10,
    ),
    "expert_mixed_signals_tight_budget": ChargebackTask(
        task_id="expert_mixed_signals_tight_budget",
        difficulty="expert",
        title="Mixed-Signal Dispute Under Time Pressure",
        objective=(
            "Handle a complex dispute with contradictory evidence and a strict step budget. "
            "Review all required evidence, identify the real threat, and close the case "
            "correctly with zero margin for error."
        ),
        case_summary=_clean(
            """
            Channel: branch-assisted urgent case
            Customer statement: "I am traveling in Paris for work and I still have my card.
            I see a 3,200.00 USD charge at a luxury store I did NOT visit. I made other
            purchases in Paris today but not this one."
            Case notes:
            - Premier client with a relationship manager
            - Travel notice for France is on file
            - Customer called from their verified mobile number while in Paris
            - Case flagged as time-sensitive by the branch
            """
        ),
        customer_profile=_clean(
            """
            - Premier checking and platinum credit card customer since 2015
            - Home city: San Francisco, California
            - Active travel notice filed for France (valid through end of month)
            - Made 4 legitimate in-store purchases in Paris today totaling 680 EUR
            - Relationship manager confirms customer is a high-value, low-risk client
            """
        ),
        transaction_details=_clean(
            """
            - Disputed charge: 3,200.00 USD at GALERIE MONTAIGNE LUXE, Paris
            - Channel: mobile wallet tap-to-pay
            - Wallet token used was provisioned 47 minutes before the transaction from a
              device the bank has NOT seen before (device ID does not match any known device)
            - The customer's legitimate Paris purchases were all made with the physical
              plastic card, not a wallet
            - No prior mobile wallet usage on this account in the last 12 months
            """
        ),
        recent_activity=_clean(
            """
            - Online banking password was reset from a Paris IP address 52 minutes before
              the disputed transaction; the IP does not match the customer's hotel Wi-Fi
            - Two failed OTP attempts preceded the successful wallet provisioning
            - After provisioning, one additional $1.00 test charge was authorized and voided
              (classic token-validation pattern)
            - Customer's own phone shows no wallet provisioning notification
            """
        ),
        policy_excerpt=_clean(
            """
            When a dispute involves a wallet token provisioned from an unrecognized device,
            preceded by a credential reset from an unknown network and failed OTP attempts,
            treat the case as account takeover regardless of whether the customer is traveling
            in the same city. The presence of legitimate physical card transactions does not
            rule out a parallel device compromise. Escalate to Fraud Ops with Urgent priority
            and initiate a fraud investigation.
            """
        ),
        expected_dispute_type="account_takeover",
        expected_priority="urgent",
        expected_team="fraud_ops",
        expected_resolution="escalate_fraud_investigation",
        required_reviews=("customer_profile", "transaction", "recent_activity", "policy"),
        max_steps=8,
    ),
}

TASK_IDS = tuple(TASKS.keys())


def get_task(task_id: str) -> ChargebackTask:
    """Return the task by identifier or raise a ValueError."""

    try:
        return TASKS[task_id]
    except KeyError as exc:
        raise ValueError(f"Unknown task_id: {task_id}") from exc


def choose_task(task_id: Optional[str] = None, seed: Optional[int] = None, cursor: int = 0) -> ChargebackTask:
    """Choose a deterministic task based on explicit id, seed, or reset cursor."""

    if task_id is not None:
        return get_task(task_id)

    if seed is not None:
        return TASKS[TASK_IDS[seed % len(TASK_IDS)]]

    return TASKS[TASK_IDS[cursor % len(TASK_IDS)]]
