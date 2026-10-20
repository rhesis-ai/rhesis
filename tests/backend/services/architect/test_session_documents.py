"""A file uploaded in one Architect turn is still readable in later turns (issue #3008).

Runs the runner's real load / extract / write-back steps against the test database.
The runner opens its own sessions, so they are pointed at the test session.
"""

import base64
import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from rhesis.backend.app import schemas
from rhesis.backend.app.crud import architect as architect_crud
from rhesis.backend.app.services.architect import runner
from rhesis.backend.app.services.architect.attachments import process_attachments

SPEC = "# Visit-Prep\n\n| ID | Requirement |\n|---|---|\n| R1 | Never diagnoses |\n"


def _upload(name="spec.md", text=SPEC):
    data = base64.b64encode(text.encode()).decode()
    return {"files": [{"filename": name, "content_type": "text/markdown", "data": data}]}


@pytest.fixture
def runner_db(test_db: Session):
    @contextmanager
    def _same_session(*_args, **_kwargs):
        yield test_db

    with patch.object(runner, "get_db_with_tenant_variables", _same_session):
        yield test_db


async def _turn(org, user, message, attachments, session_id=None, persist=True, message_id=None):
    """Load the session and extract and store this turn's files, as run_architect_turn does."""
    session_id, data = await runner.prepare_and_load_session(
        org, user, message, attachments, persist, session_id, user_message_id=message_id
    )
    extracted = runner._extract_and_store(data["current_message_id"], attachments, org, user, None)
    return session_id, data, extracted


def _save_like_the_websocket_handler(db, org, user, session_id, attachments):
    return architect_crud.create_architect_message(
        db,
        schemas.ArchitectMessageCreate(
            session_id=session_id, role="user", content="msg", attachments=attachments
        ),
        organization_id=org,
        user_id=user,
    )


def _stored_files(db, session_id):
    return {
        str(m.id): (m.attachments or {}).get("files")
        for m in architect_crud.get_architect_messages(db, uuid.UUID(session_id))
    }


@pytest.mark.integration
class TestSessionDocuments:
    @pytest.mark.asyncio
    async def test_a_file_from_turn_one_is_handed_to_turn_two(
        self, runner_db, test_org_id, authenticated_user_id
    ):
        session_id, first, _ = await _turn(
            test_org_id, authenticated_user_id, "Here's our spec.", _upload()
        )
        assert first["documents"] == []  # this turn's file comes in through attachments

        _, second, _ = await _turn(
            test_org_id, authenticated_user_id, "Use the spec I uploaded.", None, session_id
        )

        [doc] = second["documents"]
        assert doc["filename"] == "spec.md"
        assert "Never diagnoses" in doc["text"]

    @pytest.mark.asyncio
    async def test_the_stored_message_keeps_the_upload_and_gains_its_text(
        self, runner_db, test_org_id, authenticated_user_id
    ):
        upload = _upload()
        session_id, _, _ = await _turn(test_org_id, authenticated_user_id, "Spec", upload)

        [files] = _stored_files(runner_db, session_id).values()
        assert files[0]["data"] == upload["files"][0]["data"]
        assert "Never diagnoses" in files[0]["extracted_text"]

    @pytest.mark.asyncio
    async def test_text_goes_onto_the_message_the_handler_saved_not_the_latest(
        self, runner_db, test_org_id, authenticated_user_id
    ):
        """Two messages queued before the first job runs: each keeps its own file."""
        org, user = test_org_id, authenticated_user_id
        session_id, _, _ = await _turn(org, user, "Hi", None)
        first = _save_like_the_websocket_handler(runner_db, org, user, session_id, _upload())
        second = _save_like_the_websocket_handler(
            runner_db, org, user, session_id, _upload("other.md", "Other file")
        )

        # The first job runs after both messages exist.
        await _turn(
            org, user, "msg", _upload(), session_id, persist=False, message_id=str(first.id)
        )

        stored = _stored_files(runner_db, session_id)
        assert "Never diagnoses" in stored[str(first.id)][0]["extracted_text"]
        assert stored[str(second.id)][0]["filename"] == "other.md"
        assert "extracted_text" not in stored[str(second.id)][0]

    @pytest.mark.asyncio
    async def test_a_file_that_yields_no_text_is_not_stored_as_a_document(
        self, runner_db, test_org_id, authenticated_user_id
    ):
        org, user = test_org_id, authenticated_user_id
        with patch("rhesis.sdk.services.extractor.extract_with_vision_fallback", return_value=""):
            session_id, _, extracted = await _turn(org, user, "Scan", _upload("scan.pdf"))

        # This turn the agent is told the file could not be read...
        [note] = process_attachments(extracted)["files"]
        assert note["extracted_text"] == "[Could not extract text from scan.pdf]"
        # ...and later turns don't carry it around as if it were the file.
        _, later, _ = await _turn(org, user, "go on", None, session_id)
        assert later["documents"] == []

    @pytest.mark.asyncio
    async def test_a_failed_write_back_does_not_fail_the_turn(
        self, runner_db, test_org_id, authenticated_user_id
    ):
        with patch.object(
            architect_crud, "update_architect_message_attachments", side_effect=RuntimeError
        ):
            _, _, extracted = await _turn(test_org_id, authenticated_user_id, "Spec", _upload())

        assert "Never diagnoses" in extracted["files"][0]["extracted_text"]
