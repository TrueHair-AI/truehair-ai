import boto3
from flask import current_app


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
