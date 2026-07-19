from django.core.cache import cache
from .models import AccessRequest

def pending_requests(request):
    if request.user.is_authenticated and request.user.is_staff:
        count = cache.get("pending_requests_count")
        if count is None:
            count = AccessRequest.objects.filter(status='pending').count()
            cache.set("pending_requests_count", count, 60)
        return {"pending_requests_count": count}
    return {"pending_requests_count": 0}
