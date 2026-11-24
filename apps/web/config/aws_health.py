import logging

from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe


logger = logging.getLogger(__name__)


@require_safe
@never_cache
def readiness(request):
    # The ALB calls this route using the target's private IP as its Host.
    # The response is constant and does not use the request host.
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        logger.warning("Database readiness check failed.")
        return HttpResponse("unavailable\n", status=503, content_type="text/plain")
    return HttpResponse("ok\n", content_type="text/plain")


def readiness_middleware(get_response):
    def middleware(request):
        if request.path_info == "/healthz/":
            return readiness(request)
        return get_response(request)

    return middleware
