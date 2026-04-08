import unittest

from bankops_chargeback.models import ChargebackAction
from bankops_chargeback.server.chargeback_environment import ChargebackOpsEnvironment


def _run_actions(env: ChargebackOpsEnvironment, actions: list[ChargebackAction]):
    result = None
    for action in actions:
        result = env.step(action)
    return result


class ChargebackOpsEnvironmentTest(unittest.TestCase):
    def test_reset_starts_with_no_last_action_error(self):
        env = ChargebackOpsEnvironment()
        observation = env.reset(task_id="medium_subscription_confusion")

        self.assertIsNone(observation.last_action_error)

    def test_successful_action_keeps_last_action_error_empty(self):
        env = ChargebackOpsEnvironment()
        env.reset(task_id="easy_unauthorized_card_not_present")
        result = env.step(ChargebackAction(action_type="view_transaction"))

        self.assertIsNone(result.last_action_error)
        self.assertGreaterEqual(result.reward, 0)

    def test_invalid_action_sets_last_action_error(self):
        env = ChargebackOpsEnvironment()
        env.reset(task_id="easy_unauthorized_card_not_present")
        result = env.step(ChargebackAction(action_type="set_priority"))

        self.assertEqual(result.last_action_error, "Action requires a value for priority.")
        self.assertLess(result.reward, 0)

    def test_reset_loads_requested_task(self):
        env = ChargebackOpsEnvironment()
        observation = env.reset(task_id="medium_subscription_confusion")

        self.assertEqual(observation.task_id, "medium_subscription_confusion")
        self.assertEqual(observation.difficulty, "medium")
        self.assertEqual(observation.workspace.reviewed_sections, [])
        self.assertEqual(observation.reward, 0.0)

    def test_easy_case_can_score_perfectly(self):
        env = ChargebackOpsEnvironment()
        env.reset(task_id="easy_unauthorized_card_not_present")
        result = _run_actions(
            env,
            [
                ChargebackAction(action_type="view_transaction"),
                ChargebackAction(action_type="view_policy"),
                ChargebackAction(action_type="set_dispute_type", value="card_not_present_fraud"),
                ChargebackAction(action_type="set_priority", value="high"),
                ChargebackAction(action_type="assign_team", value="card_disputes"),
                ChargebackAction(action_type="set_resolution", value="approve_provisional_credit"),
                ChargebackAction(action_type="close_case"),
            ],
        )

        self.assertIsNotNone(result)
        self.assertTrue(result.done)
        self.assertTrue(result.grader.success)
        self.assertEqual(result.grader.score, 1.0)

    def test_medium_case_can_score_perfectly(self):
        env = ChargebackOpsEnvironment()
        env.reset(task_id="medium_subscription_confusion")
        result = _run_actions(
            env,
            [
                ChargebackAction(action_type="view_transaction"),
                ChargebackAction(action_type="view_recent_activity"),
                ChargebackAction(action_type="view_policy"),
                ChargebackAction(action_type="set_dispute_type", value="merchant_billing_dispute"),
                ChargebackAction(action_type="set_priority", value="medium"),
                ChargebackAction(action_type="assign_team", value="billing_disputes"),
                ChargebackAction(action_type="set_resolution", value="request_merchant_contact"),
                ChargebackAction(action_type="close_case"),
            ],
        )

        self.assertIsNotNone(result)
        self.assertTrue(result.done)
        self.assertTrue(result.grader.success)
        self.assertEqual(result.grader.score, 1.0)

    def test_hard_case_can_score_perfectly(self):
        env = ChargebackOpsEnvironment()
        env.reset(task_id="hard_wallet_account_takeover")
        result = _run_actions(
            env,
            [
                ChargebackAction(action_type="view_customer_profile"),
                ChargebackAction(action_type="view_transaction"),
                ChargebackAction(action_type="view_recent_activity"),
                ChargebackAction(action_type="view_policy"),
                ChargebackAction(action_type="set_dispute_type", value="account_takeover"),
                ChargebackAction(action_type="set_priority", value="urgent"),
                ChargebackAction(action_type="assign_team", value="fraud_ops"),
                ChargebackAction(action_type="set_resolution", value="escalate_fraud_investigation"),
                ChargebackAction(action_type="close_case"),
            ],
        )

        self.assertIsNotNone(result)
        self.assertTrue(result.done)
        self.assertTrue(result.grader.success)
        self.assertEqual(result.grader.score, 1.0)

    def test_premature_close_is_penalized(self):
        env = ChargebackOpsEnvironment()
        env.reset(task_id="easy_unauthorized_card_not_present")
        result = env.step(ChargebackAction(action_type="close_case"))

        self.assertTrue(result.done)
        self.assertFalse(result.grader.success)
        self.assertLess(result.reward, 0)

    def test_medium_duplicate_can_score_perfectly(self):
        env = ChargebackOpsEnvironment()
        env.reset(task_id="medium_duplicate_processing_error")
        result = _run_actions(
            env,
            [
                ChargebackAction(action_type="view_transaction"),
                ChargebackAction(action_type="view_customer_profile"),
                ChargebackAction(action_type="view_policy"),
                ChargebackAction(action_type="set_dispute_type", value="merchant_processing_error"),
                ChargebackAction(action_type="set_priority", value="medium"),
                ChargebackAction(action_type="assign_team", value="billing_disputes"),
                ChargebackAction(action_type="set_resolution", value="request_merchant_contact"),
                ChargebackAction(action_type="close_case"),
            ],
        )

        self.assertIsNotNone(result)
        self.assertTrue(result.done)
        self.assertTrue(result.grader.success)
        self.assertEqual(result.grader.score, 1.0)

    def test_hard_friendly_fraud_can_score_perfectly(self):
        env = ChargebackOpsEnvironment()
        env.reset(task_id="hard_friendly_fraud_denial")
        result = _run_actions(
            env,
            [
                ChargebackAction(action_type="view_customer_profile"),
                ChargebackAction(action_type="view_transaction"),
                ChargebackAction(action_type="view_recent_activity"),
                ChargebackAction(action_type="view_policy"),
                ChargebackAction(action_type="set_dispute_type", value="merchant_billing_dispute"),
                ChargebackAction(action_type="set_priority", value="low"),
                ChargebackAction(action_type="assign_team", value="billing_disputes"),
                ChargebackAction(action_type="set_resolution", value="deny_claim"),
                ChargebackAction(action_type="close_case"),
            ],
        )

        self.assertIsNotNone(result)
        self.assertTrue(result.done)
        self.assertTrue(result.grader.success)
        self.assertEqual(result.grader.score, 1.0)

    def test_expert_tight_budget_can_score_perfectly(self):
        env = ChargebackOpsEnvironment()
        env.reset(task_id="expert_mixed_signals_tight_budget")
        result = _run_actions(
            env,
            [
                ChargebackAction(action_type="view_customer_profile"),
                ChargebackAction(action_type="view_transaction"),
                ChargebackAction(action_type="view_recent_activity"),
                ChargebackAction(action_type="view_policy"),
                ChargebackAction(action_type="set_dispute_type", value="account_takeover"),
                ChargebackAction(action_type="set_priority", value="urgent"),
                ChargebackAction(action_type="assign_team", value="fraud_ops"),
                ChargebackAction(action_type="set_resolution", value="escalate_fraud_investigation"),
            ],
        )

        # After 8 steps the budget is exhausted. The case auto-closes.
        self.assertIsNotNone(result)
        self.assertTrue(result.done)
        self.assertTrue(result.grader.success)
        self.assertEqual(result.grader.score, 1.0)

    def test_expert_tight_budget_wasted_step_hurts(self):
        """If the agent wastes a step on the expert case, it runs out of budget."""
        env = ChargebackOpsEnvironment()
        env.reset(task_id="expert_mixed_signals_tight_budget")
        # Waste a step by viewing an unrequired section twice won't happen,
        # but viewing all 4 + setting 4 values = 8 steps with no room for close_case.
        # If we waste one step, we can't set all values.
        result = _run_actions(
            env,
            [
                ChargebackAction(action_type="view_customer_profile"),
                ChargebackAction(action_type="view_customer_profile"),  # wasted repeat
                ChargebackAction(action_type="view_transaction"),
                ChargebackAction(action_type="view_recent_activity"),
                ChargebackAction(action_type="view_policy"),
                ChargebackAction(action_type="set_dispute_type", value="account_takeover"),
                ChargebackAction(action_type="set_priority", value="urgent"),
                ChargebackAction(action_type="assign_team", value="fraud_ops"),
            ],
        )

        self.assertTrue(result.done)
        # The case was auto-closed due to budget exhaustion.
        # Resolution was never set, so it cannot be a full success.
        self.assertFalse(result.grader.success)


if __name__ == "__main__":
    unittest.main()
