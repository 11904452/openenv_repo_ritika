import unittest

from bankops_chargeback.server.web_ui import (
    action_requires_value,
    get_default_task_id,
    get_task_choices,
    value_options_for_action,
)


class ChargebackWebUiHelpersTest(unittest.TestCase):
    def test_difficult_group_includes_hard_and_expert(self):
        choices = get_task_choices("difficult")
        self.assertIn("hard_wallet_account_takeover", choices)
        self.assertIn("hard_friendly_fraud_denial", choices)
        self.assertIn("expert_mixed_signals_tight_budget", choices)

    def test_easy_group_defaults_to_easy_task(self):
        self.assertEqual(
            get_default_task_id("easy"),
            "easy_unauthorized_card_not_present",
        )

    def test_value_required_only_for_set_actions(self):
        self.assertTrue(action_requires_value("set_dispute_type"))
        self.assertTrue(action_requires_value("set_priority"))
        self.assertTrue(action_requires_value("assign_team"))
        self.assertTrue(action_requires_value("set_resolution"))
        self.assertFalse(action_requires_value("view_transaction"))
        self.assertFalse(action_requires_value("close_case"))

    def test_value_options_match_action(self):
        self.assertEqual(
            value_options_for_action("assign_team"),
            ["card_disputes", "billing_disputes", "fraud_ops", "digital_wallet_ops"],
        )


if __name__ == "__main__":
    unittest.main()
