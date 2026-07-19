from tracking.models import WeightMeasurement


def get_bmr_for_user(user, date=None, default_weight=70.0):
    """Get calculated BMR for a user, optionally looking up recent weight."""
    weight = default_weight
    weight_qs = WeightMeasurement.objects.filter(user=user)
    if date:
        weight_qs = weight_qs.filter(date__lte=date).order_by("-date", "-created_at")
    else:
        weight_qs = weight_qs.order_by("-date", "-created_at")
    last_w = weight_qs.first()
    if not last_w and not date:
        last_w = WeightMeasurement.objects.filter(user=user).order_by("date", "created_at").first()
    if last_w:
        weight = float(last_w.weight)
    return user.calculate_bmr(weight), weight
