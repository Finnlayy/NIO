import unittest

from orchestrator.telegram.models import (
    ApprovalRequest,
    ApprovalStatus,
    Direction,
    InvalidTransitionError,
    Signal,
    Suggestion,
    SuggestionStatus,
    TgDialog,
    TgMessage,
    check_transition,
)


class TestTelegramModels(unittest.TestCase):
    def test_tg_dialog_roundtrip(self):
        d = TgDialog(id=123, name="Test", kind="user", is_bot=False, unread=5)
        d_dict = d.to_dict()
        d2 = TgDialog.from_dict(d_dict)
        self.assertEqual(d, d2)

    def test_tg_message_roundtrip(self):
        m = TgMessage(peer=123, msg_id=1, sender="Sender", text="Text", ts="2023-01-01T00:00:00Z", outgoing=False, is_bot=False)
        m_dict = m.to_dict()
        m2 = TgMessage.from_dict(m_dict)
        self.assertEqual(m, m2)

    def test_suggestion_roundtrip(self):
        s = Suggestion(
            id="1",
            source_peer=1,
            target_peer=2,
            text="text",
            based_on_msg_id=10,
            origin="llm",
            status=SuggestionStatus.PENDING,
            created_at="now",
            decided_at=None,
            error=None,
        )
        s_dict = s.to_dict()
        self.assertEqual(s_dict["status"], "pending")
        s2 = Suggestion.from_dict(s_dict)
        self.assertEqual(s, s2)

    def test_approval_request_roundtrip(self):
        a = ApprovalRequest(
            id="1",
            request_id="req-1",
            title="Title",
            detail="Detail",
            status=ApprovalStatus.PENDING,
            created_at="now",
            decided_at=None,
            callback_url=None,
        )
        a_dict = a.to_dict()
        self.assertEqual(a_dict["status"], "pending")
        a2 = ApprovalRequest.from_dict(a_dict)
        self.assertEqual(a, a2)

    def test_signal_roundtrip(self):
        s = Signal(
            id="1",
            symbol="BTC",
            direction=Direction.BULLISH,
            strength=8,
            peer=123,
            msg_id=10,
            evidence="evidence",
            created_at="now",
            kanban_task_id=None,
        )
        s_dict = s.to_dict()
        self.assertEqual(s_dict["direction"], "bullish")
        s2 = Signal.from_dict(s_dict)
        self.assertEqual(s, s2)

    def test_suggestion_transitions(self):
        check_transition("suggestion", SuggestionStatus.PENDING, SuggestionStatus.SENDING)
        check_transition("suggestion", SuggestionStatus.PENDING, SuggestionStatus.DISMISSED)

        with self.assertRaises(InvalidTransitionError):
            check_transition("suggestion", SuggestionStatus.PENDING, SuggestionStatus.SENT)

        with self.assertRaises(InvalidTransitionError):
            check_transition("suggestion", SuggestionStatus.SENT, SuggestionStatus.PENDING)

    def test_approval_transitions(self):
        check_transition("approval", ApprovalStatus.PENDING, ApprovalStatus.APPROVED)
        check_transition("approval", ApprovalStatus.PENDING, ApprovalStatus.REJECTED)

        with self.assertRaises(InvalidTransitionError):
            check_transition("approval", ApprovalStatus.APPROVED, ApprovalStatus.PENDING)


if __name__ == "__main__":
    unittest.main()
