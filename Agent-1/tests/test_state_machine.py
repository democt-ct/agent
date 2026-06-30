"""状态机单元测试."""
import pytest

from app.mcp.state_machine import (
    InvalidSessionStateTransition,
    SessionState,
    SessionStateMachine,
)


class TestSessionStateMachine:
    """测试会话状态机的基础转换."""

    def test_initial_state_is_idle(self):
        fsm = SessionStateMachine(session_id="test-1")
        assert fsm.current_state == SessionState.IDLE

    def test_idle_to_identifying(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        assert fsm.current_state == SessionState.IDENTIFYING
        assert len(fsm.history) == 1

    def test_identifying_to_triage(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.transition(SessionState.TRIAGE)
        assert fsm.current_state == SessionState.TRIAGE

    def test_triage_to_consulting(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.transition(SessionState.TRIAGE)
        fsm.transition(SessionState.CONSULTING)
        assert fsm.current_state == SessionState.CONSULTING

    def test_consulting_to_follow_up(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.transition(SessionState.TRIAGE)
        fsm.transition(SessionState.CONSULTING)
        fsm.transition(SessionState.FOLLOW_UP)
        assert fsm.current_state == SessionState.FOLLOW_UP

    def test_follow_up_to_completed(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.transition(SessionState.TRIAGE)
        fsm.transition(SessionState.CONSULTING)
        fsm.transition(SessionState.FOLLOW_UP)
        fsm.transition(SessionState.COMPLETED)
        assert fsm.current_state == SessionState.COMPLETED

    def test_consulting_back_to_triage(self):
        """允许在咨询中因新症状回到分流."""
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.transition(SessionState.TRIAGE)
        fsm.transition(SessionState.CONSULTING)
        fsm.transition(SessionState.TRIAGE)
        assert fsm.current_state == SessionState.TRIAGE

    def test_follow_up_back_to_consulting(self):
        """允许随访中因新问题回到咨询."""
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.transition(SessionState.TRIAGE)
        fsm.transition(SessionState.CONSULTING)
        fsm.transition(SessionState.FOLLOW_UP)
        fsm.transition(SessionState.CONSULTING)
        assert fsm.current_state == SessionState.CONSULTING


class TestEscalation:
    """测试人工升级路径."""

    def test_escalate_from_identifying(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.escalate()
        assert fsm.current_state == SessionState.HUMAN_ESCALATION

    def test_escalate_from_triage(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.transition(SessionState.TRIAGE)
        fsm.escalate()
        assert fsm.current_state == SessionState.HUMAN_ESCALATION

    def test_escalate_from_consulting(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.transition(SessionState.TRIAGE)
        fsm.transition(SessionState.CONSULTING)
        fsm.escalate()
        assert fsm.current_state == SessionState.HUMAN_ESCALATION

    def test_cannot_escalate_from_idle(self):
        fsm = SessionStateMachine(session_id="test-1")
        with pytest.raises(InvalidSessionStateTransition):
            fsm.escalate()

    def test_cannot_escalate_from_completed(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.transition(SessionState.TRIAGE)
        fsm.transition(SessionState.CONSULTING)
        fsm.transition(SessionState.FOLLOW_UP)
        fsm.complete()
        assert fsm.is_terminal(fsm.current_state)
        with pytest.raises(InvalidSessionStateTransition):
            fsm.escalate()


class TestInvalidTransitions:
    """测试非法转换."""

    def test_idle_to_consulting_not_allowed(self):
        fsm = SessionStateMachine(session_id="test-1")
        with pytest.raises(InvalidSessionStateTransition):
            fsm.transition(SessionState.CONSULTING)

    def test_idle_to_completed_not_allowed(self):
        fsm = SessionStateMachine(session_id="test-1")
        with pytest.raises(InvalidSessionStateTransition):
            fsm.transition(SessionState.COMPLETED)

    def test_completed_cannot_transition(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.transition(SessionState.TRIAGE)
        fsm.transition(SessionState.CONSULTING)
        fsm.complete()
        with pytest.raises(InvalidSessionStateTransition):
            fsm.transition(SessionState.IDLE)

    def test_triage_cannot_go_direct_to_follow_up(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.transition(SessionState.TRIAGE)
        with pytest.raises(InvalidSessionStateTransition):
            fsm.transition(SessionState.FOLLOW_UP)

    def test_identifying_cannot_go_to_consulting(self):
        """必须先 triage 才能 consulting."""
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        with pytest.raises(InvalidSessionStateTransition):
            fsm.transition(SessionState.CONSULTING)


class TestSerialization:
    """测试序列化/反序列化."""

    def test_to_dict_and_from_dict(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.transition(SessionState.TRIAGE)
        
        data = fsm.to_dict()
        assert data["session_id"] == "test-1"
        assert data["current_state"] == SessionState.TRIAGE
        assert len(data["history"]) == 2

        restored = SessionStateMachine.from_dict(data)
        assert restored.session_id == "test-1"
        assert restored.current_state == SessionState.TRIAGE
        assert len(restored.history) == 2

    def test_reset_from_terminal(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        fsm.transition(SessionState.TRIAGE)
        fsm.transition(SessionState.CONSULTING)
        fsm.complete()
        assert fsm.current_state == SessionState.COMPLETED
        fsm.reset()
        assert fsm.current_state == SessionState.IDLE
        assert len(fsm.history) == 0

    def test_cannot_reset_from_non_terminal(self):
        fsm = SessionStateMachine(session_id="test-1")
        fsm.transition(SessionState.IDENTIFYING)
        with pytest.raises(InvalidSessionStateTransition):
            fsm.reset()


class TestHelperMethods:
    """测试辅助方法."""

    def test_can_transition_classmethod(self):
        assert SessionStateMachine.can_transition(SessionState.IDLE, SessionState.IDENTIFYING)
        assert not SessionStateMachine.can_transition(SessionState.IDLE, SessionState.CONSULTING)
        assert not SessionStateMachine.can_transition(SessionState.COMPLETED, SessionState.IDLE)

    def test_can_escalate_classmethod(self):
        assert SessionStateMachine.can_escalate(SessionState.IDENTIFYING)
        assert SessionStateMachine.can_escalate(SessionState.CONSULTING)
        assert not SessionStateMachine.can_escalate(SessionState.IDLE)
        assert not SessionStateMachine.can_escalate(SessionState.COMPLETED)

    def test_is_terminal(self):
        assert SessionStateMachine.is_terminal(SessionState.COMPLETED)
        assert SessionStateMachine.is_terminal(SessionState.HUMAN_ESCALATION)
        assert SessionStateMachine.is_terminal(SessionState.TIMEOUT)
        assert not SessionStateMachine.is_terminal(SessionState.CONSULTING)
        assert not SessionStateMachine.is_terminal(SessionState.IDLE)
