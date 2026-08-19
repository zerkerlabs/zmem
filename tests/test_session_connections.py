import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zerker_memory.session_connections import (
    consume_session_invitation,
    create_session_invitation,
    create_session_invitations,
    detach_session_attachment,
    list_session_attachments,
    touch_session_attachments,
)
from zerker_memory.store import MemoryStore


class SessionConnectionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "memory.sqlite")
        self.store.init()
        self.now = datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.store.conn.close()
        self.tmp.cleanup()

    def test_invitation_is_hashed_bound_and_single_use(self):
        code = "zma_test-code-with-enough-entropy"
        invitation = create_session_invitation(
            self.store.conn,
            agent_id="codex",
            scope="project",
            room_id="rom_release",
            session_label="release chat",
            now=self.now,
            code=code,
        )

        stored = self.store.conn.execute(
            "SELECT code_hash, consumed_at FROM session_invitations WHERE invitation_id = ?",
            (invitation["invitation_id"],),
        ).fetchone()
        self.assertNotEqual(stored["code_hash"], code)
        self.assertNotIn(code, stored["code_hash"])
        self.assertIsNone(stored["consumed_at"])
        self.assertEqual(invitation["room_membership_authority"], "gateway")

        with self.assertRaisesRegex(ValueError, "bound to agent codex"):
            consume_session_invitation(
                self.store.conn,
                activation_code=code,
                agent_id="claude-code",
                connection_id="conn_wrong",
                now=self.now,
            )

        attachment = consume_session_invitation(
            self.store.conn,
            activation_code=code,
            agent_id="codex",
            connection_id="conn_123",
            client_session_id="chat_abc",
            now=self.now,
        )
        self.assertEqual(attachment["presence"], "live")
        self.assertEqual(attachment["identity_assurance"], "client_asserted")
        self.assertEqual(attachment["room_id"], "rom_release")

        with self.assertRaisesRegex(ValueError, "already been used"):
            consume_session_invitation(
                self.store.conn,
                activation_code=code,
                agent_id="codex",
                connection_id="conn_replay",
                now=self.now,
            )

    def test_batch_invitations_are_atomic(self):
        repeated_code = "zma_repeated-code-with-enough-entropy"

        with self.assertRaises(sqlite3.IntegrityError):
            create_session_invitations(
                self.store.conn,
                agent_ids=["codex", "claude-code"],
                now=self.now,
                codes=[repeated_code, repeated_code],
            )

        stored_count = self.store.conn.execute("SELECT COUNT(*) FROM session_invitations").fetchone()[0]
        self.assertEqual(stored_count, 0)

    def test_batch_collision_with_existing_invitation_rolls_back_new_invitations(self):
        existing_code = "zma_existing-code-with-enough-entropy"
        create_session_invitation(
            self.store.conn,
            agent_id="codex",
            now=self.now,
            code=existing_code,
        )

        with self.assertRaises(sqlite3.IntegrityError):
            create_session_invitations(
                self.store.conn,
                agent_ids=["claude-code", "hermes"],
                now=self.now,
                codes=["zma_new-code-with-enough-entropy", existing_code],
            )

        stored_codes = self.store.conn.execute(
            "SELECT agent_id FROM session_invitations ORDER BY created_at, invitation_id"
        ).fetchall()
        self.assertEqual([row[0] for row in stored_codes], ["codex"])

    def test_expired_invitation_is_rejected(self):
        code = "zma_expired-code-with-enough-entropy"
        create_session_invitation(
            self.store.conn,
            agent_id="codex",
            ttl_seconds=30,
            now=self.now,
            code=code,
        )

        with self.assertRaisesRegex(ValueError, "has expired"):
            consume_session_invitation(
                self.store.conn,
                activation_code=code,
                agent_id="codex",
                connection_id="conn_late",
                now=self.now + timedelta(seconds=31),
            )

    def test_presence_moves_from_live_to_idle_and_detached(self):
        code = "zma_presence-code-with-enough-entropy"
        create_session_invitation(
            self.store.conn,
            agent_id="hermes",
            now=self.now,
            code=code,
        )
        attachment = consume_session_invitation(
            self.store.conn,
            activation_code=code,
            agent_id="hermes",
            connection_id="conn_hermes",
            now=self.now,
        )

        idle = list_session_attachments(
            self.store.conn,
            agent_id="hermes",
            now=self.now + timedelta(seconds=121),
        )
        self.assertEqual(idle["idle_count"], 1)
        self.assertEqual(idle["attachments"][0]["presence"], "idle")

        touched = touch_session_attachments(
            self.store.conn,
            connection_id="conn_hermes",
            now=self.now + timedelta(seconds=122),
        )
        self.assertEqual(touched, 1)
        live = list_session_attachments(
            self.store.conn,
            connection_id="conn_hermes",
            now=self.now + timedelta(seconds=123),
        )
        self.assertEqual(live["live_count"], 1)

        detached = detach_session_attachment(
            self.store.conn,
            attachment_id=attachment["attachment_id"],
            detached_by="operator://local",
            reason="handoff complete",
            now=self.now + timedelta(seconds=124),
        )
        self.assertEqual(detached["state"], "detached")
        self.assertEqual(detached["presence"], "detached")
        self.assertEqual(detached["detach_reason"], "handoff complete")
        self.assertEqual(
            touch_session_attachments(
                self.store.conn,
                connection_id="conn_hermes",
                now=self.now + timedelta(seconds=125),
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
