from collections import defaultdict
from datetime import date as date_type, datetime
from statistics import mean
from django.utils import timezone
from tracking.models import MeasurementSession, WeightMeasurement, PhysicalActivityLog, FoodLog, DailyActivityLog


def _simple_linear_regression(xs, ys):
    """Simple linear regression returning slope (coef_) and intercept."""
    n = len(xs)
    if n < 2:
        return 0.0, 0.0
    x_mean = mean(xs)
    y_mean = mean(ys)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den = sum((x - x_mean) ** 2 for x in xs)
    if den == 0:
        return 0.0, y_mean
    slope = num / den
    intercept = y_mean - slope * x_mean
    return slope, intercept


def _multi_linear_regression(x_matrix, y_vals):
    """Multi-variable linear regression via normal equation (X^T X)^{-1} X^T y.
    Each row of x_matrix is a list of predictors.
    """
    n = len(x_matrix)
    if n < 3:
        return [0.0] * len(x_matrix[0]) if x_matrix else []
    m = len(x_matrix[0])
    X = [[1.0] + list(row) for row in x_matrix]
    Xt = list(zip(*X))
    XtX = [[sum(a * b for a, b in zip(Xt_i, Xt_j)) for Xt_j in Xt] for Xt_i in Xt]
    XtY = [sum(a * b for a, b in zip(Xt_i, y_vals)) for Xt_i in Xt]
    try:
        import numpy.linalg as la
        import numpy as np
        beta = la.solve(np.array(XtX), np.array(XtY))
        return beta.tolist()[1:]
    except ImportError:
        pass
    n_vars = m + 1
    aug = [row[:] + [XtY[i]] for i, row in enumerate(XtX)]
    for i in range(n_vars):
        pivot = aug[i][i]
        if abs(pivot) < 1e-12:
            continue
        for j in range(i + 1, n_vars):
            factor = aug[j][i] / pivot
            for k in range(i, n_vars + 1):
                aug[j][k] -= factor * aug[i][k]
    beta = [0.0] * n_vars
    for i in range(n_vars - 1, -1, -1):
        beta[i] = aug[i][n_vars] / aug[i][i] if abs(aug[i][i]) > 1e-12 else 0.0
        for j in range(i - 1, -1, -1):
            aug[j][n_vars] -= aug[j][i] * beta[i]
    return beta[1:]


def generate_insights(user):
    today = timezone.now().date()
    thirty_days_ago = today - timezone.timedelta(days=30)

    activities_qs = PhysicalActivityLog.objects.filter(user=user, date__gte=thirty_days_ago).select_related("activity")
    foods_qs = FoodLog.objects.filter(user=user, date__gte=thirty_days_ago).prefetch_related("items__food", "items__recipe__ingredients__food")
    weights_qs = WeightMeasurement.objects.filter(user=user, date__gte=thirty_days_ago)
    sessions_qs = MeasurementSession.objects.filter(user=user, date__gte=thirty_days_ago)
    daily_qs = DailyActivityLog.objects.filter(user=user, date__gte=thirty_days_ago)

    has_activities = activities_qs.exists()
    has_foods = foods_qs.exists()
    has_weights = weights_qs.exists()
    has_sessions = sessions_qs.exists()
    has_daily = daily_qs.exists()

    if not (has_activities or has_foods or has_weights or has_sessions or has_daily):
        return {"insights": [], "timeline_labels": [], "weight_data": [], "sport_data": []}

    # Build daily dicts
    daily = {}

    for log in activities_qs:
        d = daily.setdefault(log.date, {})
        d.setdefault("sport_duration", 0)
        d["sport_duration"] += log.duration_minutes or 0
        if log.not_tracked_by_watch:
            d["extra_exercise_calories"] = d.get("extra_exercise_calories", 0) + (log.estimated_calories or 0)

    for f in foods_qs:
        d = daily.setdefault(f.date, {})
        d["eat_out_count"] = d.get("eat_out_count", 0) + (1 if f.eaten_out else 0)
        d["daily_calories"] = d.get("daily_calories", 0.0) + f.get_total_calories()

    for w in weights_qs:
        d = daily.setdefault(w.date, {})
        if "weight" not in d:
            d["weight"] = float(w.weight)
        else:
            d["weight"] = mean([d["weight"], float(w.weight)])

    for s in sessions_qs:
        d = daily.setdefault(s.date, {})
        if s.avg_systolic is not None:
            vals = d.setdefault("avg_sys_list", [])
            vals.append(s.avg_systolic)

    for da in daily_qs:
        d = daily.setdefault(da.date, {})
        for k in ("active_calories", "resting_calories", "steps"):
            old = d.get(k, 0)
            d[k] = old + getattr(da, k, 0) if k != "steps" else old + (da.steps or 0)
        d["distance_km"] = d.get("distance_km", 0.0) + float(da.distance_km or 0)

    sorted_dates = sorted(daily.keys())
    if not sorted_dates:
        return {"insights": [], "timeline_labels": [], "weight_data": [], "sport_data": []}

    # Forward-fill weight and avg_sys
    last_weight = None
    last_sys = None
    user_height = user.height_cm
    user_gender = user.gender
    user_birth = user.birth_date
    age = 35
    if user_birth:
        age = today.year - user_birth.year - ((today.month, today.day) < (user_birth.month, user_birth.day))
    fallback_bmr = 1800 if user_gender == "male" else 1400
    constant = 5 if user_gender == "male" else -161

    for d in sorted_dates:
        row = daily[d]
        if "weight" in row:
            last_weight = row["weight"]
        else:
            row["weight"] = last_weight
        if "avg_sys_list" in row:
            last_sys = mean(row.pop("avg_sys_list"))
        row["avg_sys"] = last_sys
        row.setdefault("sport_duration", 0)
        row.setdefault("extra_exercise_calories", 0)
        row.setdefault("eat_out_count", 0)
        row.setdefault("daily_calories", 0.0)
        row.setdefault("active_calories", 0)
        row.setdefault("steps", 0)
        row.setdefault("distance_km", 0.0)

        resting = row.get("resting_calories")
        if not resting:
            w = row.get("weight") or 70.0
            if user_height and user_birth and user_gender:
                resting = 10.0 * w + 6.25 * user_height - 5.0 * age + constant
            else:
                resting = fallback_bmr
        row["resting_calories"] = resting
        row["total_expenditure"] = resting + row["active_calories"] + row["extra_exercise_calories"]
        row["caloric_balance"] = row["daily_calories"] - row["total_expenditure"]

    # Compute diffs (next day - current)
    for i in range(len(sorted_dates) - 1):
        curr = daily[sorted_dates[i]]
        nxt = daily[sorted_dates[i + 1]]
        curr["weight_next"] = nxt.get("weight")
        curr["sys_next"] = nxt.get("avg_sys")
        if curr.get("weight") is not None and curr["weight_next"] is not None:
            curr["weight_diff"] = curr["weight_next"] - curr["weight"]
        if curr.get("avg_sys") is not None and curr.get("sys_next") is not None:
            curr["sys_diff"] = curr["sys_next"] - curr["avg_sys"]

    insights = []

    # 1. Caloric balance vs weight change regression
    bal_weight = [(r["caloric_balance"], r["weight_diff"]) for r in [daily[d] for d in sorted_dates[:-1]]
                  if r.get("caloric_balance") is not None and r.get("weight_diff") is not None]
    if len(bal_weight) >= 7:
        xs = [b[0] for b in bal_weight]
        ys = [b[1] for b in bal_weight]
        slope, _ = _simple_linear_regression(xs, ys)
        if slope > 1e-5:
            gramos_por_500 = slope * 500 * 1000
            insights.append({
                "type": "success", "icon": "bi-fire",
                "title": "Impacto del Balance Calórico",
                "text": f"Nuestra IA estima que por cada 500 kcal de déficit diario acumulado, tu peso disminuye en media {gramos_por_500:.0f}g al día siguiente. Mantén el balance calórico negativo para asegurar la pérdida."
            })
        else:
            insights.append({
                "type": "success", "icon": "bi-arrow-down-circle",
                "title": "Control Calórico Activo",
                "text": "Has comenzado a registrar balance calórico. Mantener un balance negativo diario constante es la vía garantizada para perder peso."
            })
    else:
        insights.append({
            "type": "info", "icon": "bi-info-circle",
            "title": "Control calórico activado",
            "text": "Sigue registrando tus calorías ingeridas (comidas) y quemadas (Apple Watch y ejercicio) para que la IA personalice tus tasas metabólicas reales."
        })

    # 2. Sport + calories vs weight change (multi regression)
    sport_data_for_reg = [(r["sport_duration"], r["daily_calories"], r["weight_diff"])
                          for r in [daily[d] for d in sorted_dates[:-1]]
                          if r.get("weight_diff") is not None]
    if len(sport_data_for_reg) >= 10:
        X = [(s[0], s[1]) for s in sport_data_for_reg]
        y = [s[2] for s in sport_data_for_reg]
        coefs = _multi_linear_regression(X, y)
        if coefs and coefs[0] < -0.001:
            gramos_por_30 = abs(coefs[0] * 30 * 1000)
            insights.append({
                "type": "success", "icon": "bi-lightning-charge",
                "title": "Impacto del Deporte",
                "text": f"Por cada 30 minutos de deporte diario (incluyendo ejercicio no monitorizado), tu peso disminuye en media {gramos_por_30:.0f}g al día siguiente."
            })

    # 3. Eat out impact on systolic
    eatout_sys = [(r["sport_duration"], r["eat_out_count"], r["sys_diff"])
                  for r in [daily[d] for d in sorted_dates[:-1]]
                  if r.get("sys_diff") is not None]
    if len(eatout_sys) >= 10:
        X = [(e[0], e[1]) for e in eatout_sys]
        y = [e[2] for e in eatout_sys]
        coefs = _multi_linear_regression(X, y)
        if coefs and len(coefs) > 1 and coefs[1] > 1.0:
            insights.append({
                "type": "danger", "icon": "bi-heart-pulse",
                "title": "Alerta de Sodio / Comidas Fuera",
                "text": f"Comer fuera de casa está aumentando tu presión sistólica media en +{coefs[1]:.1f} mmHg. ¡Vigila el exceso de sal en restaurantes!"
            })

    # 4. Eat out impact on weight
    eatout_weight = [(r["eat_out_count"], r["weight_diff"], r["daily_calories"])
                     for r in [daily[d] for d in sorted_dates[:-1]]
                     if r.get("weight_diff") is not None]
    has_eaten_out = any(r.get("eat_out_count", 0) > 0 for r in daily.values())
    if len(eatout_weight) >= 5:
        days_eo = [r for r in eatout_weight if r[0] > 0]
        days_home = [r for r in eatout_weight if r[0] == 0]
        avg_cal_eo = mean(r[2] for r in days_eo) if days_eo else 0.0
        avg_cal_home = mean(r[2] for r in days_home) if days_home else 0.0
        xs = [r[0] for r in eatout_weight]
        ys = [r[1] for r in eatout_weight]
        slope_eo, _ = _simple_linear_regression(xs, ys)
        if slope_eo > 0.0:
            gramos_por_comida = slope_eo * 1000
            text = f"Comer fuera de casa se asocia con un incremento estimado de {gramos_por_comida:.0f}g en tu peso al día siguiente."
            diff_cal = avg_cal_eo - avg_cal_home if avg_cal_home > 0 else 0
            if diff_cal > 0:
                text += f" En promedio, consumes {diff_cal:.0f} kcal más los días que comes fuera de casa ({avg_cal_eo:.0f} kcal vs {avg_cal_home:.0f} kcal)."
            insights.append({
                "type": "warning", "icon": "bi-exclamation-triangle",
                "title": "Impacto de Comer Fuera de Casa",
                "text": text
            })
        elif has_eaten_out:
            insights.append({
                "type": "info", "icon": "bi-info-circle",
                "title": "Comidas Fuera de Casa",
                "text": "Has registrado comidas fuera de casa. La IA está analizando cómo estas comidas afectan tu peso y balance calórico diario."
            })
    elif has_eaten_out:
        insights.append({
            "type": "warning", "icon": "bi-exclamation-triangle",
            "title": "Impacto de Comer Fuera de Casa",
            "text": "Comer fuera de casa incrementa significativamente tu ingesta calórica diaria (estimado en +500 kcal y un 30% extra de grasa/sodio por comida). Procura limitar estas comidas para evitar desvíos en tu peso."
        })

    # 5. Daily coaching tip
    target_weekly_loss = float(user.target_weekly_loss_kg or 0.5)
    required_daily_deficit = (target_weekly_loss * 7700.0) / 7.0
    last_date = sorted_dates[-1]
    last_row = daily[last_date]
    last_intake = last_row["daily_calories"]
    last_exp = last_row["total_expenditure"]
    last_bal = last_row["caloric_balance"]
    target_balance = -required_daily_deficit

    if last_bal > target_balance:
        extra_needed = last_bal - target_balance
        extra_steps = (extra_needed / 45.0) * 1000.0
        latest_w = last_row.get("weight") or 75.0
        karate_kcal_per_min = (8.0 * latest_w) / 60.0
        karate_min = extra_needed / karate_kcal_per_min if karate_kcal_per_min > 0 else extra_needed / 10.0
        insights.append({
            "type": "warning", "icon": "bi-bullseye",
            "title": "Consejo de Objetivo Semanal",
            "text": f"Para mantener tu ritmo de pérdida de {target_weekly_loss} kg/semana, necesitas un déficit diario de {required_daily_deficit:.0f} kcal (balance de {target_balance:.0f} kcal). Ayer tu balance fue de {last_bal:.0f} kcal. Para compensar hoy, te aconsejamos dar {extra_steps:.0f} pasos más o entrenar Karate por {karate_min:.0f} minutos."
        })
    else:
        insights.append({
            "type": "success", "icon": "bi-trophy",
            "title": "¡Objetivo de Balance Superado!",
            "text": f"¡Ayer lograste un balance de {last_bal:.0f} kcal, superando tu objetivo de déficit de {required_daily_deficit:.0f} kcal! Mantén esta constancia para asegurar tu progreso."
        })

    # 6. Timeline data for charts
    timeline_labels = []
    weight_data = []
    sport_data = []
    for d in sorted_dates:
        row = daily[d]
        if row.get("weight") is not None or row["sport_duration"] > 0:
            timeline_labels.append(d.strftime("%Y-%m-%d"))
            weight_data.append(row.get("weight"))
            sport_data.append(row["sport_duration"])

    return {
        "insights": insights,
        "timeline_labels": timeline_labels,
        "weight_data": weight_data,
        "sport_data": sport_data,
    }
