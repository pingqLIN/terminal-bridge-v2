"""Tests for tb2.intervention — InterventionLayer."""

from tb2.intervention import Action, InterventionLayer, PendingMessage


class TestInterventionInactive:
    def test_submit_auto_when_inactive(self):
        layer = InterventionLayer(active=False)
        msg = layer.submit("a", "b", "hello")
        assert msg.action == Action.AUTO
        assert layer.list_pending() == []

    def test_submit_returns_pending_message(self):
        layer = InterventionLayer(active=False)
        msg = layer.submit("a", "b", "hello")
        assert isinstance(msg, PendingMessage)
        assert msg.from_pane == "a"
        assert msg.to_pane == "b"
        assert msg.text == "hello"


class TestInterventionActive:
    def test_submit_pending_when_active(self):
        layer = InterventionLayer(active=True)
        msg = layer.submit("a", "b", "hello")
        assert msg.action == Action.PENDING
        assert len(layer.list_pending()) == 1

    def test_approve(self):
        layer = InterventionLayer(active=True)
        msg = layer.submit("a", "b", "hello")
        result = layer.approve(msg.id)
        assert result is not None
        assert result.action == Action.APPROVED
        assert layer.list_pending() == []

    def test_reject(self):
        layer = InterventionLayer(active=True)
        msg = layer.submit("a", "b", "hello")
        result = layer.reject(msg.id)
        assert result is not None
        assert result.action == Action.REJECTED
        assert layer.list_pending() == []

    def test_edit(self):
        layer = InterventionLayer(active=True)
        msg = layer.submit("a", "b", "hello")
        result = layer.edit(msg.id, "edited text")
        assert result is not None
        assert result.action == Action.EDITED
        assert result.edited_text == "edited text"
        assert layer.list_pending() == []

    def test_approve_nonexistent(self):
        layer = InterventionLayer(active=True)
        assert layer.approve(999) is None

    def test_reject_nonexistent(self):
        layer = InterventionLayer(active=True)
        assert layer.reject(999) is None

    def test_edit_nonexistent(self):
        layer = InterventionLayer(active=True)
        assert layer.edit(999, "text") is None

    def test_approve_all(self):
        layer = InterventionLayer(active=True)
        for i in range(3):
            layer.submit("a", "b", f"msg {i}")
        approved = layer.approve_all()
        assert len(approved) == 3
        assert all(m.action == Action.APPROVED for m in approved)
        assert layer.list_pending() == []

    def test_reject_all(self):
        layer = InterventionLayer(active=True)
        for i in range(3):
            layer.submit("a", "b", f"msg {i}")
        count = layer.reject_all()
        assert count == 3
        assert layer.list_pending() == []

    def test_approve_already_resolved(self):
        layer = InterventionLayer(active=True)
        msg = layer.submit("a", "b", "hello")
        layer.approve(msg.id)
        assert layer.approve(msg.id) is None


class TestPauseResume:
    def test_pause_activates(self):
        layer = InterventionLayer(active=False)
        layer.pause()
        assert layer.active is True
        msg = layer.submit("a", "b", "test")
        assert msg.action == Action.PENDING

    def test_resume_deactivates(self):
        layer = InterventionLayer(active=True)
        layer.resume()
        assert layer.active is False
        msg = layer.submit("a", "b", "test")
        assert msg.action == Action.AUTO


class TestAutoIncrementId:
    def test_ids_increment(self):
        layer = InterventionLayer(active=True)
        m1 = layer.submit("a", "b", "first")
        m2 = layer.submit("a", "b", "second")
        assert m2.id == m1.id + 1
