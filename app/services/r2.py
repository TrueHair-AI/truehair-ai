import uuid

import boto3
from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _get_s3_client():
    """Return a boto3 S3 client configured for Cloudflare R2."""
    account_id = current_app.config["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=current_app.config["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=current_app.config["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def make_upload_key(filename):
    """Generate a unique R2 object key for a user upload."""
    safe = secure_filename(filename) if filename else "photo"
    return f"uploads/{uuid.uuid4()}_{safe}"


def make_generated_key():
    """Generate a unique R2 object key for a generated image."""
    return f"uploads/gen_{uuid.uuid4()}.png"


def get_presigned_put_url(key, content_type="image/jpeg", expires_in=3600):
    """Return a presigned PUT URL for the given object key."""
    client = _get_s3_client()
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": current_app.config["R2_BUCKET_NAME"],
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )


def get_presigned_get_url(key, expires_in=3600):
    """Return a presigned GET URL for the given object key."""
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": current_app.config["R2_BUCKET_NAME"],
            "Key": key,
        },
        ExpiresIn=expires_in,
    )


def upload_bytes(key, data, content_type="image/png"):
    """Upload raw bytes to R2 under the given key."""
    client = _get_s3_client()
    client.put_object(
        Bucket=current_app.config["R2_BUCKET_NAME"],
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def download_bytes(key):
    """Download an object from R2 and return its bytes."""
    client = _get_s3_client()
    response = client.get_object(
        Bucket=current_app.config["R2_BUCKET_NAME"],
        Key=key,
    )
    return response["Body"].read()


def get_display_url(image_url):
    """Return a presigned GET URL for an image stored in R2.

    Returns None if image_url is falsy (e.g. no image yet).
    """
    if not image_url:
        return None
    return get_presigned_get_url(image_url)
