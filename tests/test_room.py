"""Tests for tb2.room — Room, RoomMessage, registry."""

import time
from unittest.mock import patch

import pytest

from tb2.room import Room, create_room, delete_room, get_room, list_rooms, cleanup_stale


class TestRoom:
    def test_post_returns_message(self, sample_room):
        msg = sample_room.post(author="test", text="hello")
        assert msg.author == "test"
        assert msg.text == "hello"
        assert msg.kind == "chat"
        assert msg.id == 6  # 5 pre-populated + 1

    def test_post_increments_id(self):
        room = Room("test")
        m1 = room.post(author="a", text="first")
        m2 = room.post(author="a", text="second")
        assert m2.id == m1.id + 1

    def test_message_count(self, sample_room):
        assert sample_room.message_count == 5

    def test_latest_id(self, sample_room):
        assert sample_room.latest_id == 5

    def test_poll_all(self, sample_room):
        msgs = sample_room.poll(after_id=0, limit=50)
        assert len(msgs) == 5

    def test_poll_after_id(self, sample_room):
        msgs = sample_room.poll(after_id=3, limit=50)
        assert len(msgs) == 2
        assert msgs[0].id == 4

    def test_poll_updates_last_active(self):
        room = Room("active-test")
        room.post(author="a", text="hello")
        before = room.last_active
        time.sleep(0.01)
        room.poll(after_id=0, limit=10)
        assert room.last_active > before

    def test_poll_with_limit(self, sample_room):
        msgs = sample_room.poll(after_id=0, limit=2)
        assert len(msgs) == 2

    def test_poll_empty_room(self):
        room = Room("empty")
        assert room.poll() == []

    def test_bounded_deque(self):
        room = Room("bounded", max_messages=5)
        for i in range(10):
            room.post(author="a", text=f"msg {i}")
        assert room.message_count == 5
        msgs = room.poll(after_id=0, limit=50)
        assert msgs[0].text == "msg 5"

    def test_post_with_meta(self):
        room = Room("meta-test")
        msg = room.post(author="a", text="hello", meta={"pane": "test:0.0"})
        assert msg.meta == {"pane": "test:0.0"}

    def test_post_with_kind(self):
        room = Room("kind-test")
        msg = room.post(author="a", text="hello", kind="system")
        assert msg.kind == "system"

    def test_subscribe_replays_backlog_then_new_messages(self):
        room = Room("live")
        room.post(author="host", text="first")
        room.post(author="guest", text="second")

        sub = room.subscribe(after_id=0, backlog_limit=10)
        backlog = sub.get(timeout=0.0, limit=10)
        room.post(author="host", text="third")
        fresh = sub.get(timeout=0.1, limit=10)

        assert [msg.text for msg in backlog] == ["first", "second"]
        assert [msg.text for msg in fresh] == ["third"]
        sub.close()

    def test_subscription_closes_when_room_closes(self):
        room = Room("closing")
        sub = room.subscribe()
        room.close()

        try:
            sub.get(timeout=0.0)
        except EOFError:
            pass
        else:
            raise AssertionError("expected EOFError for closed subscription")


class TestRoomRegistry:
    def test_create_room(self):
        room = create_room("my-room")
        assert room.room_id == "my-room"

    def test_create_room_auto_id(self):
        room = create_room()
        assert len(room.room_id) == 12

    def test_create_room_invalid_id_raises(self):
        with pytest.raises(ValueError, match="invalid room_id"):
            create_room("bad room id")

    def test_create_room_idempotent(self):
        r1 = create_room("same")
        r2 = create_room("same")
        assert r1 is r2

    def test_get_room(self):
        create_room("find-me")
        assert get_room("find-me") is not None

    def test_get_room_not_found(self):
        assert get_room("nonexistent") is None

    def test_list_rooms(self):
        create_room("r1")
        create_room("r2")
        rooms = list_rooms()
        ids = [r.room_id for r in rooms]
        assert "r1" in ids
        assert "r2" in ids

    def test_delete_room(self):
        create_room("to-delete")
        assert delete_room("to-delete") is True
        assert get_room("to-delete") is None

    def test_delete_nonexistent(self):
        assert delete_room("nope") is False

    def test_cleanup_stale(self):
        room = create_room("stale")
        room.last_active = time.time() - 7200  # 2 hours ago
        removed = cleanup_stale(ttl_seconds=3600)
        assert removed == 1
        assert get_room("stale") is None

    def test_cleanup_keeps_active(self):
        create_room("active")
        removed = cleanup_stale(ttl_seconds=3600)
        assert removed == 0
        assert get_room("active") is not None
