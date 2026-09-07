import json
import time
import uuid


class SecurityMiddleware:
    """Bounded request buffering also protects chunked multipart requests."""

    def __init__(self, app, max_bytes: int, production: bool = False):
        self.app, self.max_bytes, self.production = app, max_bytes, production

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        headers = dict(scope.get("headers", []))
        body = bytearray()
        try:
            if int(headers.get(b"content-length", b"0")) > self.max_bytes:
                raise OverflowError
            while True:
                event = await receive()
                if event["type"] == "http.disconnect":
                    return
                body.extend(event.get("body", b""))
                if len(body) > self.max_bytes:
                    raise OverflowError
                if not event.get("more_body", False):
                    break
        except (ValueError, OverflowError):
            await send(
                {
                    "type": "http.response.start",
                    "status": 413,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            return await send(
                {
                    "type": "http.response.body",
                    "body": json.dumps(
                        {
                            "error": {"code": "UPLOAD_SIZE", "message": "Request exceeds size limit."},
                            "request_id": request_id,
                        }
                    ).encode(),
                }
            )
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        async def secure_send(message):
            if message["type"] == "http.response.start":
                h = message.setdefault("headers", [])
                h.extend(
                    [
                        (b"x-request-id", request_id.encode()),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"cache-control", b"no-store"),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                        (
                            b"content-security-policy",
                            b"default-src 'self'; script-src 'self'; style-src 'self'; "
                            b"img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; "
                            b"form-action 'self'; frame-ancestors 'none'",
                        ),
                    ]
                )
                if self.production:
                    h.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
            await send(message)

        started = time.monotonic()
        await self.app(scope, replay, secure_send)
        # Never log cookies, image data, prompts, usernames or query strings.
        import logging

        logging.getLogger("furniture.http").info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": scope["method"],
                    "duration_ms": round((time.monotonic() - started) * 1000),
                }
            )
        )
