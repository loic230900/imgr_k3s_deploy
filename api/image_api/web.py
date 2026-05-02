import os
from email.utils import formatdate
from urllib.parse import unquote

import config
from botocore.exceptions import ClientError
from celery.canvas import group
from flask import Flask, redirect, request, url_for
from flask.typing import ResponseReturnValue
from flask_cors import CORS
from opentelemetry.instrumentation.flask import FlaskInstrumentor

from .storage import bucket, s3
from .utils import random_id, valid_id
from .worker import Sizes, resize_image

# Create the bucket if it does not exist
if bucket.creation_date is None:
    try:
        bucket.create()
    except ClientError as e:
        if e.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
            raise

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)  # type: ignore[no-untyped-call]

# Origines CORS lues depuis CORS_ALLOWED_ORIGINS, defaut "*" pour le dev local.
# En prod, backend-deploy.yml fixe la valeur au domaine de l'app.
_cors_env = os.environ.get("CORS_ALLOWED_ORIGINS", "*").strip()
_cors_origins: str | list[str] = (
    "*" if _cors_env == "*" else [o.strip() for o in _cors_env.split(",") if o.strip()]
)
CORS(app, origins=_cors_origins)


@app.route("/")
def index() -> dict[str, str]:
    return {
        "upload_url": unquote(url_for("upload")),
        "original_image_url": unquote(url_for("original", id="{id}")),
        "big_image_url": unquote(url_for("big", id="{id}")),
        "medium_image_url": unquote(url_for("medium", id="{id}")),
        "small_image_url": unquote(url_for("small", id="{id}")),
        "tiny_image_url": unquote(url_for("tiny", id="{id}")),
    }


@app.route("/image", methods=["POST"])
def upload() -> ResponseReturnValue:
    """Upload the image to the S3 bucket"""
    if "file" not in request.files:
        return {"error": "missing file"}, 400

    file = request.files["file"]
    # Generate a random ID. It should be random enough to not have collisions
    id = random_id()

    bucket.Object(f"{Sizes.Original.segment}/{id}").upload_fileobj(
        file.stream,
        ExtraArgs={"ContentType": file.content_type},
    )

    group(
        [
            resize_image.s(key=id, size=Sizes.Big),
            resize_image.s(key=id, size=Sizes.Medium),
            resize_image.s(key=id, size=Sizes.Small),
            resize_image.s(key=id, size=Sizes.Tiny),
        ]
    ).delay()

    return {
        "id": id,
        "original": url_for("original", id=id),
        "big": url_for("big", id=id),
        "medium": url_for("medium", id=id),
        "small": url_for("small", id=id),
        "tiny": url_for("tiny", id=id),
    }, 201


def stream_image(id: str, size: Sizes) -> ResponseReturnValue:
    # Fail fast if the ID does not have the right shape
    if not valid_id(id):
        return "invalid id", 400

    key = f"{size.segment}/{id}"

    # Production: redirect the client straight to S3 via a presigned URL
    if config.s3["endpoint_url"] is None:
        try:
            bucket.Object(key).load()
        except ClientError as ex:
            code = ex.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey"):
                return "not found", 404
            raise
        url = s3.meta.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": config.bucket_name, "Key": key},
            ExpiresIn=3600,
        )
        return redirect(url)

    # Local dev: proxy bytes through Flask
    # Forward the If-None-Match and If-Modified-Since headers
    args = {}
    if_none_match = request.headers.get("If-None-Match")
    if if_none_match is not None:
        args["IfNoneMatch"] = if_none_match
    if_modified_since = request.headers.get("If-Modified-Since")
    if if_modified_since is not None:
        args["IfModifiedSince"] = if_modified_since

    try:
        obj = bucket.Object(f"{size.segment}/{id}").get(**args)
    except s3.meta.client.exceptions.NoSuchKey:
        # If the key was not found, return a 404
        return "not found", 404
    except ClientError as ex:
        # If the request returned a 304, forward it
        err = ex.response.get("Error")
        if err is not None and err.get("Code") == "304":
            return "", 304
        # Else, for other errors, re-raise
        raise

    res = app.response_class(obj["Body"], mimetype=obj["ContentType"])
    # Forward a few headers from the GetObject response
    res.headers.add("Content-Length", str(obj["ContentLength"]))
    res.headers.add("ETag", obj["ETag"])
    res.headers.add(
        "Last-Modified", formatdate(obj["LastModified"].timestamp(), usegmt=True)
    )
    res.headers.add("Cache-Control", "public")

    return res


@app.route("/image/<id>", methods=["GET"])
def original(id: str) -> ResponseReturnValue:
    """Serve the original image from the S3 bucket"""
    return stream_image(id, Sizes.Original)


@app.route("/image/<id>/big", methods=["GET"])
def big(id: str) -> ResponseReturnValue:
    """Serve the big thumbnail image from the S3 bucket"""
    return stream_image(id, Sizes.Big)


@app.route("/image/<id>/medium", methods=["GET"])
def medium(id: str) -> ResponseReturnValue:
    """Serve the medium thumbnail image from the S3 bucket"""
    return stream_image(id, Sizes.Medium)


@app.route("/image/<id>/small", methods=["GET"])
def small(id: str) -> ResponseReturnValue:
    """Serve the small thumbnail image from the S3 bucket"""
    return stream_image(id, Sizes.Small)


@app.route("/image/<id>/tiny", methods=["GET"])
def tiny(id: str) -> ResponseReturnValue:
    """Serve the tiny thumbnail image from the S3 bucket"""
    return stream_image(id, Sizes.Tiny)


@app.route("/health", methods=["GET"])
def health() -> ResponseReturnValue:
    """Healthcheck route. Returns build identity for ops visibility."""
    return {
        "ok": True,
        "version": os.environ.get("APP_VERSION", "unknown"),
        "git_sha": os.environ.get("GIT_SHA", "unknown"),
        "build_date": os.environ.get("BUILD_DATE", "unknown"),
    }


def dev() -> None:
    app.run(host="0.0.0.0", port=8080, debug=True, use_reloader=False)


if __name__ == "__main__":
    # When the script is being run standalone, start the Flask debug server
    dev()
