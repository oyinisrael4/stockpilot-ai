"""Same-origin production SPA and bundled public assets; never serve workspace files."""
import mimetypes
from pathlib import Path
from django.conf import settings
from django.http import FileResponse, Http404


def frontend(request, path=""):
    if not settings.SERVE_FRONTEND: raise Http404()
    root = Path(settings.FRONTEND_DIST).resolve()
    showcase = path == "showcase" or path.startswith("showcase/")
    if showcase:
        root = root.parent / "dist-showcase"
        path = path.removeprefix("showcase").lstrip("/")
    if path.startswith(("assets/", "portfolio/")):
        target = (root / path).resolve()
        if not target.is_relative_to(root) or not target.is_file(): raise Http404()
    elif path and ("." in path or path.startswith("api")):
        raise Http404()
    else:
        target = root / "index.html"
        if not target.is_file(): raise Http404()
    content_type = {".js": "text/javascript", ".css": "text/css", ".webp": "image/webp"}.get(target.suffix)
    response = FileResponse(target.open("rb"), content_type=content_type or mimetypes.guess_type(str(target))[0] or "application/octet-stream")
    response["Cache-Control"] = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-store"
    response["Content-Security-Policy"] = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' https: data:; connect-src 'self'; media-src 'self' blob:; font-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")
    response["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=()"
    if showcase:
        response["Content-Security-Policy"] = response["Content-Security-Policy"].replace("connect-src 'self'", "connect-src 'none'").replace("media-src 'self' blob:", "media-src 'none'")
        response["Permissions-Policy"] = "microphone=(), camera=(), geolocation=()"
    return response
