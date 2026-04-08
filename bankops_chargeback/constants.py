"""Shared constants for the banking chargeback operations environment."""

from enum import Enum


class ActionType(str, Enum):
    VIEW_CUSTOMER_PROFILE = "view_customer_profile"
    VIEW_TRANSACTION = "view_transaction"
    VIEW_RECENT_ACTIVITY = "view_recent_activity"
    VIEW_POLICY = "view_policy"
    SET_DISPUTE_TYPE = "set_dispute_type"
    SET_PRIORITY = "set_priority"
    ASSIGN_TEAM = "assign_team"
    SET_RESOLUTION = "set_resolution"
    CLOSE_CASE = "close_case"


ACTION_TYPES = tuple(action.value for action in ActionType)

SECTION_NAMES = (
    "customer_profile",
    "transaction",
    "recent_activity",
    "policy",
)

SECTION_TO_ACTION = {
    "customer_profile": ActionType.VIEW_CUSTOMER_PROFILE.value,
    "transaction": ActionType.VIEW_TRANSACTION.value,
    "recent_activity": ActionType.VIEW_RECENT_ACTIVITY.value,
    "policy": ActionType.VIEW_POLICY.value,
}

SECTION_TITLES = {
    "customer_profile": "Customer Profile",
    "transaction": "Transaction Details",
    "recent_activity": "Recent Activity",
    "policy": "Policy Excerpt",
}

DISPUTE_TYPES = (
    "card_not_present_fraud",
    "merchant_billing_dispute",
    "merchant_processing_error",
    "account_takeover",
)

PRIORITIES = (
    "low",
    "medium",
    "high",
    "urgent",
)

TEAMS = (
    "card_disputes",
    "billing_disputes",
    "fraud_ops",
    "digital_wallet_ops",
)

RESOLUTIONS = (
    "approve_provisional_credit",
    "deny_claim",
    "request_merchant_contact",
    "escalate_fraud_investigation",
)

ALLOWED_VALUES = {
    "action_type": list(ACTION_TYPES),
    "dispute_type": list(DISPUTE_TYPES),
    "priority": list(PRIORITIES),
    "team": list(TEAMS),
    "resolution": list(RESOLUTIONS),
}
