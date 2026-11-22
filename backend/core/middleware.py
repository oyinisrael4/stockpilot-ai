from django.http import JsonResponse


class ApiPrivacyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            if len(request.META.get("QUERY_STRING", "")) > 4096:
                return JsonResponse({"detail": "Query string is too large."}, status=414)
            if request.content_type == "application/json" and request.encoding not in (None, "utf-8", "utf8"):
                return JsonResponse({"detail": "JSON requests must use UTF-8."}, status=415)
            search = request.GET.get("search", "")
            if len(search) > 200 or len(search.split()) > 12:
                return JsonResponse({"detail": "Use a search of at most 200 characters and 12 words."}, status=400)
            accept = request.META.get("HTTP_ACCEPT", "")
            if len(accept) > 4096 or accept.count(",") > 31:
                return JsonResponse({"detail": "Accept header is too large."}, status=431)
            try:
                length = int(request.META.get("CONTENT_LENGTH") or 0)
            except ValueError:
                return JsonResponse({"detail": "Invalid content length."}, status=400)
            if length > 2 * 1024 * 1024:
                return JsonResponse({"detail": "Request body is too large."}, status=413)
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store, private"
            response["Pragma"] = "no-cache"
        response.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
        return response
