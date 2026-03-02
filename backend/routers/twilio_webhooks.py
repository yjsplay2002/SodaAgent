"""Twilio TwiML webhook endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter(prefix="/api/twilio", tags=["twilio"])


@router.post("/voice")
async def voice_webhook(request: Request):
    """Handle incoming Twilio voice webhook for outbound calls.

    Returns TwiML to connect the call to our Media Streams WebSocket.
    """
    form = await request.form()
    call_sid = form.get("CallSid", "unknown")

    backend_url = "soda-agent.run.app"  # TODO: Get from env
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{backend_url}/ws/twilio/{call_sid}" />
    </Connect>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/status")
async def status_callback(request: Request):
    """Handle Twilio call status callbacks."""
    form = await request.form()
    call_sid = form.get("CallSid")
    call_status = form.get("CallStatus")

    # TODO: Update call status in Firestore
    return {"call_sid": call_sid, "status": call_status}
