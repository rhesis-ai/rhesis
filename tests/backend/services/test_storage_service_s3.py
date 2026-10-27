"""StorageService against an S3-compatible endpoint, served by moto.

s3fs goes through aiobotocore, which moto's in-process ``mock_aws`` can't
intercept, so these tests run moto's threaded server and point
``STORAGE_SERVICE_ENDPOINT`` at it, the same way a SeaweedFS or MinIO
deployment does. No ``AWS_*`` variables are set: configuration must arrive
through the ``STORAGE_SERVICE_*`` settings alone.
"""

import os
from unittest.mock import patch

import boto3
import pytest
import s3fs
from moto.server import ThreadedMotoServer

from rhesis.backend.app.services.storage_service import (
    StorageConfigurationError,
    StorageService,
)

BUCKET = "test-bucket"
ACCESS_KEY = "rhesis-access"
SECRET_KEY = "rhesis-secret"
REGION = "eu-central-1"


@pytest.fixture(scope="module")
def s3_endpoint():
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0)
    server.start()
    host, port = server.get_host_and_port()
    yield f"http://{host}:{port}"
    server.stop()


@pytest.fixture
def s3_client(s3_endpoint):
    client = boto3.client(
        "s3",
        endpoint_url=s3_endpoint,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION,
    )
    client.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION})
    yield client
    for obj in client.list_objects_v2(Bucket=BUCKET).get("Contents", []):
        client.delete_object(Bucket=BUCKET, Key=obj["Key"])
    client.delete_bucket(Bucket=BUCKET)


@pytest.fixture
def s3_storage(s3_endpoint, s3_client):
    env = {
        "STORAGE_SERVICE_URI": f"s3://{BUCKET}",
        "STORAGE_SERVICE_ENDPOINT": s3_endpoint,
        "STORAGE_SERVICE_ACCESS_KEY": ACCESS_KEY,
        "STORAGE_SERVICE_SECRET_KEY": SECRET_KEY,
        "STORAGE_SERVICE_REGION": REGION,
    }
    with patch.dict(os.environ, env, clear=True):
        # fsspec caches filesystem instances; a cached one would carry another test's settings.
        s3fs.S3FileSystem.clear_instance_cache()
        yield StorageService()
        s3fs.S3FileSystem.clear_instance_cache()


def _object_keys(client):
    return {obj["Key"] for obj in client.list_objects_v2(Bucket=BUCKET).get("Contents", [])}


@pytest.mark.unit
class TestStorageServiceS3:
    def test_settings_reach_s3fs(self, s3_storage, s3_endpoint):
        fs = s3_storage.fs
        assert s3_storage.use_cloud_storage is True
        assert isinstance(fs, s3fs.S3FileSystem)
        assert fs.endpoint_url == s3_endpoint
        assert fs.key == ACCESS_KEY
        assert fs.secret == SECRET_KEY
        assert fs.client_kwargs == {"region_name": REGION}
        assert fs.config_kwargs == {"s3": {"addressing_style": "path"}}

    @pytest.mark.asyncio
    async def test_legacy_api_roundtrip(self, s3_storage, s3_client):
        file_path = s3_storage.get_source_path("org-1", "src-1", "doc.pdf")
        assert file_path == f"{BUCKET}/org-1/src-1_doc.pdf"

        await s3_storage.save_file(b"legacy bytes", file_path)
        assert _object_keys(s3_client) == {"org-1/src-1_doc.pdf"}
        assert await s3_storage.get_file(file_path) == b"legacy bytes"

        assert await s3_storage.delete_file(file_path) is True
        assert _object_keys(s3_client) == set()

    @pytest.mark.asyncio
    async def test_object_api_roundtrip(self, s3_storage, s3_client):
        path = "attachments/org-1/Test/eid/fid/original.bin"
        data = b"object bytes" * 2000  # spans several CHUNK_SIZE reads

        assert s3_storage.put_object_bytes(data, path, "application/octet-stream")[0] == path
        assert _object_keys(s3_client) == {path}

        stream = await s3_storage.get_object_stream(path)
        assert b"".join([chunk async for chunk in stream]) == data
        assert b"".join(s3_storage.iter_object(path)) == data

        # S3 deletes are idempotent, so a second remove_object also returns True.
        assert s3_storage.remove_object(path) is True
        assert _object_keys(s3_client) == set()


@pytest.mark.unit
@patch("rhesis.backend.app.services.storage_service.fsspec.filesystem")
def test_unset_s3_settings_leave_default_credential_chain(mock_filesystem):
    with patch.dict(os.environ, {"STORAGE_SERVICE_URI": f"s3://{BUCKET}"}, clear=True):
        StorageService()

    mock_filesystem.assert_called_once_with("s3")


@pytest.mark.unit
class TestStorageServiceFailsLoudly:
    def test_s3_init_failure_raises(self):
        with (
            patch.dict(os.environ, {"STORAGE_SERVICE_URI": f"s3://{BUCKET}"}, clear=True),
            patch(
                "rhesis.backend.app.services.storage_service.fsspec.filesystem",
                side_effect=ImportError("Install s3fs to access S3"),
            ),
        ):
            with pytest.raises(StorageConfigurationError, match="s3://test-bucket"):
                StorageService()

    def test_gcs_without_key_raises(self):
        with patch.dict(os.environ, {"STORAGE_SERVICE_URI": "gs://some-bucket"}, clear=True):
            with pytest.raises(StorageConfigurationError, match="STORAGE_SERVICE_ACCOUNT_KEY"):
                StorageService()

    def test_unknown_scheme_raises(self):
        with patch.dict(os.environ, {"STORAGE_SERVICE_URI": "minio://some-bucket"}, clear=True):
            with pytest.raises(StorageConfigurationError, match="unsupported scheme"):
                StorageService()

    def test_cloud_uri_without_bucket_raises(self):
        with patch.dict(os.environ, {"STORAGE_SERVICE_URI": "s3://"}, clear=True):
            with pytest.raises(StorageConfigurationError, match="names no bucket"):
                StorageService()
