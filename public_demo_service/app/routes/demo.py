from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.events import event_hub
from app.topology import topology_payload

router = APIRouter(tags=["demo"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def demo_home(request: Request) -> HTMLResponse:
    settings = get_settings()
    return templates.TemplateResponse(
        request,
        "demo.html",
        {
            "service_name": settings.service_name,
            "gateway_url": settings.api_gateway_url,
        },
    )


@router.get("/api/topology/{view}")
async def get_topology(view: str) -> dict:
    if view not in {"business", "microservices"}:
        view = "business"
    return topology_payload(view)


@router.websocket("/ws/events")
async def events_ws(websocket: WebSocket) -> None:
    await event_hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await event_hub.disconnect(websocket)
