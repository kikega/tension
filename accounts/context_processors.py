from .models import AccessRequest

def pending_requests(request):
    """
    Context processor to add the number of pending access requests
    to the template context for staff/admin users.
    """
    if request.user.is_authenticated and request.user.is_staff:
        return {
            'pending_requests_count': AccessRequest.objects.filter(status='pending').count()
        }
    return {
        'pending_requests_count': 0
    }
