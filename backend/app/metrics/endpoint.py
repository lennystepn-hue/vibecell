from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.metrics.registry import REGISTRY

router = APIRouter()


@router.get("/metrics")
async def metrics_endpoint() -> Response:
    body = generate_latest(REGISTRY)
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)
