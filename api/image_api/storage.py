import boto3
import config
from botocore.client import Config

s3_kwargs = dict(config.s3)

if s3_kwargs.get("endpoint_url") is None:
    region = s3_kwargs.get("region_name") or "us-east-1"
    s3_kwargs["endpoint_url"] = f"https://s3.{region}.amazonaws.com"

s3 = boto3.resource(
    "s3",
    **s3_kwargs,
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "virtual"},
    ),
)

bucket = s3.Bucket(config.bucket_name)

__all__ = ["s3", "bucket"]
