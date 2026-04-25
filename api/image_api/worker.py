import enum
from io import BytesIO
from typing import Any

from celery import Celery
from celery.signals import worker_process_init
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from PIL import Image

from .storage import bucket

@worker_process_init.connect(weak=False)
def init_celery_tracing(*args: Any, **kwargs: Any) -> None:
    CeleryInstrumentor().instrument()

app = Celery(__name__, config_source="config.celery")

app.conf.update(
    task_time_limit=120,
    task_soft_time_limit=90,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
)

class Sizes(enum.IntEnum):
    Original = 10_000_000
    Big = 1024
    Medium = 512
    Small = 256
    Tiny = 128

    @property
    def segment(self) -> str:
        return self.name.lower()

def format_map(format: str) -> str:
    if format == "image/png":
        return "PNG"
    if format == "image/jpeg":
        return "JPEG"
    if format == "image/gif":
        return "GIF"
    raise Exception("unsupported image type")

@app.task
def resize_image(key: str, size: Sizes) -> None:
    size = Sizes(size)
    if size == Sizes.Original:
        return

    obj = bucket.Object(f"{Sizes.Original.segment}/{key}").get()
    bytes = obj["Body"].read()
    img = Image.open(BytesIO(bytes))
    img.thumbnail((int(size), int(size)))

    buffer = BytesIO()
    img.save(buffer, format_map(obj["ContentType"]))
    buffer.seek(0)

    new_key = f"{size.segment}/{key}"
    bucket.Object(new_key).put(Body=buffer, ContentType=obj["ContentType"])

__all__ = ["resize_image", "Sizes", "format_map"]
