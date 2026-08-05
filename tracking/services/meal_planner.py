from datetime import date, timedelta
from collections import defaultdict
from statistics import mean
from tracking.models import FoodLog, WeightMeasurement, DailyActivityLog

# ── Fixed recommendations ────────────────────────────────────────────────────
# Nutritional values are totals for the specified serving (NOT per 100g)

BREAKFAST_TEMPLATE = {
    "name": "Desayuno",
    "target_pct": (0.35, 0.40),
    "foods": [
        {"name": "Huevos enteros", "qty_str": "3 ud", "protein": 18, "fat": 15, "carbs": 1, "kcal": 210},
        {"name": "Avena", "qty_str": "60 g", "protein": 7, "fat": 4, "carbs": 40, "kcal": 230},
        {"name": "Fruta (plátano/frutos rojos)", "qty_str": "1 ud", "protein": 1, "fat": 0, "carbs": 25, "kcal": 105},
        {"name": "Frutos secos", "qty_str": "25 g", "protein": 5, "fat": 14, "carbs": 3, "kcal": 160},
        {"name": "Yogur natural / kéfir", "qty_str": "1 ud", "protein": 8, "fat": 5, "carbs": 6, "kcal": 100},
    ],
}

DINNER_TEMPLATE = {
    "name": "Cena",
    "target_pct": (0.15, 0.20),
    "foods": [
        {"name": "Batido de caseína", "qty_str": "30 g", "protein": 24, "fat": 1, "carbs": 3, "kcal": 120},
        {"name": "Yogur o queso fresco", "qty_str": "1 ud", "protein": 10, "fat": 4, "carbs": 5, "kcal": 95},
        {"name": "Nueces", "qty_str": "12 g", "protein": 2, "fat": 7, "carbs": 1, "kcal": 75},
    ],
}

SUPPLEMENTS = [
    {"name": "Vitamina D", "qty": "2000-4000 UI/día"},
    {"name": "Omega 3 (EPA/DHA)", "qty": "1-2 g/día"},
    {"name": "Creatina", "qty": "5 g/día"},
    {"name": "Multivitamínico", "qty": "1 comprimido/día"},
    {"name": "Magnesio", "qty": "Ya cubierto"},
]

TARGET_KCAL_RANGE = (2200, 2400)
# Objetivo dinámico: márgenes de seguridad amplios en lugar de un rango fijo
MIN_DAILY_KCAL = 1400
MAX_DAILY_KCAL = 3500


def _sum_foods(foods):
    return {
        "protein": round(sum(f["protein"] for f in foods)),
        "fat": round(sum(f["fat"] for f in foods)),
        "carbs": round(sum(f["carbs"] for f in foods)),
        "kcal": round(sum(f["kcal"] for f in foods)),
    }


BREAKFAST_TOTALS = _sum_foods(BREAKFAST_TEMPLATE["foods"])
DINNER_TOTALS = _sum_foods(DINNER_TEMPLATE["foods"])


def _simple_linear_regression(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0, 0.0
    x_m = mean(xs)
    y_m = mean(ys)
    num = sum((x - x_m) * (y - y_m) for x, y in zip(xs, ys))
    den = sum((x - x_m) ** 2 for x in xs)
    if den == 0:
        return 0.0, y_m
    return num / den, y_m - (num / den) * x_m


def _compute_lunch_macros(kcal_target, body_weight):
    lunch_kcal = kcal_target * 0.47
    protein_g = round(2.0 * body_weight)
    protein_kcal = protein_g * 4
    fat_g = 20
    fat_kcal = fat_g * 9
    carbs_kcal = lunch_kcal - protein_kcal - fat_kcal
    carbs_g = max(100, round(carbs_kcal / 4))
    return {
        "protein": protein_g,
        "fat": fat_g,
        "carbs": carbs_g,
        "kcal": round(protein_kcal + fat_g * 9 + carbs_g * 4),
    }


def _adjust_macros_to_kcal(macros, target_kcal):
    """Scale macros proportionally to hit a target kcal."""
    current = macros["protein"] * 4 + macros["fat"] * 9 + macros["carbs"] * 4
    if current == 0:
        return macros
    factor = target_kcal / current
    return {
        "protein": round(macros["protein"] * factor),
        "fat": round(macros["fat"] * factor),
        "carbs": round(macros["carbs"] * factor),
        "kcal": round(target_kcal),
    }


class AdaptiveMealPlanner:
    """
    Generates daily meal plans based on user profile and recommendations.
    Learns from historical food logs to adapt portions over time.
    """

    def __init__(self, user):
        self.user = user
        self._load_history()
        self._calibrate()

    def _load_history(self):
        thirty_days_ago = date.today() - timedelta(days=60)
        self.food_logs = list(
            FoodLog.objects.filter(user=self.user, date__gte=thirty_days_ago)
            .prefetch_related("items__food", "items__recipe__ingredients__food")
            .order_by("date")
        )
        self.weights = list(
            WeightMeasurement.objects.filter(user=self.user, date__gte=thirty_days_ago)
            .order_by("date")
        )
        self.daily_activity = list(
            DailyActivityLog.objects.filter(user=self.user, date__gte=thirty_days_ago)
            .order_by("date")
        )

        # Ingesta diaria por fecha (cálculo único para todos los usos)
        by_date = defaultdict(list)
        for fl in self.food_logs:
            by_date[fl.date].append(fl)
        self.intake_by_date = {
            d: sum(fl.get_total_calories() for fl in logs)
            for d, logs in by_date.items()
        }

    def _estimate_tdee(self):
        """Estima el gasto energético diario (TDEE) real combinando la relación
        ingesta↔peso y el gasto total medido por dispositivo/ejercicio."""
        estimates = []  # (peso_del_periodo, tdee)
        weights = sorted(self.weights, key=lambda w: w.date)
        for i in range(len(weights) - 1):
            w0, w1 = weights[i], weights[i + 1]
            days = (w1.date - w0.date).days
            if days <= 0 or days > 21:
                continue
            span_intake = [
                cal for d, cal in self.intake_by_date.items() if w0.date <= d < w1.date
            ]
            if not span_intake or mean(span_intake) <= 0:
                continue
            avg_intake = mean(span_intake)
            delta_kg = float(w1.weight) - float(w0.weight)
            imbalance_per_day = (delta_kg * 7700.0) / days  # negativo si hay pérdida
            tdee = avg_intake - imbalance_per_day
            if 800 < tdee < 6000:
                estimates.append((days, tdee))

        activity_estimates = [
            da.get_total_calories_burned() for da in self.daily_activity
        ]
        activity_estimates = [e for e in activity_estimates if 800 < e < 6000]

        if estimates and activity_estimates:
            total_days = sum(w for w, _ in estimates)
            from_weight = sum(w * t for w, t in estimates) / total_days
            from_activity = mean(activity_estimates)
            return 0.5 * from_weight + 0.5 * from_activity
        if estimates:
            total_days = sum(w for w, _ in estimates)
            return sum(w * t for w, t in estimates) / total_days
        if activity_estimates:
            return mean(activity_estimates)
        return None

    def _weight_trend_has_data(self) -> bool:
        return len(self.weights) >= 3

    def _weekday_active_profile(self):
        """Gasto medio por día de la semana para modular el objetivo diario
        según el patrón real de ejercicio del usuario."""
        self.active_by_weekday = {wd: 0.0 for wd in range(7)}
        if not self.daily_activity:
            return
        expenditures = [da.get_total_calories_burned() for da in self.daily_activity]
        overall = mean(expenditures)
        by_weekday = defaultdict(list)
        for da in self.daily_activity:
            by_weekday[da.date.weekday()].append(da.get_total_calories_burned())
        for wd in range(7):
            vals = by_weekday.get(wd, [])
            avg = mean(vals) if vals else overall
            self.active_by_weekday[wd] = avg - overall

    def _calibrate(self):
        weight = 70.0
        if self.weights:
            weight = float(self.weights[-1].weight)
        self.current_weight = weight

        bmr = self.user.calculate_bmr(weight)

        # 1) TDEE estimado a partir de los datos reales (no un valor constante)
        tdee = self._estimate_tdee()
        if tdee is None:
            avg_active = 0.0
            if self.daily_activity:
                avg_active = mean(
                    da.active_calories + da.extra_exercise_calories for da in self.daily_activity
                )
            tdee = float(bmr) + avg_active
            if tdee < float(bmr) * 1.1:
                tdee = float(bmr) * 1.2
        self.tdee = tdee

        # 2) Déficit meta según el objetivo semanal del usuario
        target_loss_kg = float(self.user.target_weekly_loss_kg or 0.5)
        daily_deficit = (target_loss_kg * 7700.0) / 7.0
        base = tdee - daily_deficit

        # 3) Retroalimentación por tendencia real de peso: si va más rápido/lento
        #    de lo objetivo, se ajusta el consumo para alinearlo.
        adjust = 0.0
        if self._weight_trend_has_data():
            slope = self._weight_trend()
            expected_slope = -target_loss_kg / 7.0
            error = slope - expected_slope  # >0 pierde lento/gana; <0 pierde rápido
            if error > 0.004:
                adjust = -min(300.0, error * 7700.0)
            elif error < -0.004:
                adjust = min(300.0, abs(error) * 7700.0)
        base = base + adjust

        # 4) Suavizado leve con la ingesta real reciente para converger de forma gradual
        if self.intake_by_date:
            avg_intake = mean(self.intake_by_date.values())
            if avg_intake > 0:
                base = 0.7 * base + 0.3 * avg_intake

        self.base_daily_kcal = max(MIN_DAILY_KCAL, min(MAX_DAILY_KCAL, round(base)))

        # 5) Perfil de ejercicio por día de la semana (objetivo no constante)
        self._weekday_active_profile()
        self.daily_kcal = self.target_kcal_for(date.today())

        protein_per_kg = 2.0
        self.target_protein = round(protein_per_kg * weight)
        self.target_fat = round(self.base_daily_kcal * 0.25 / 9)
        self.target_carbs = round(
            (self.base_daily_kcal - self.target_protein * 4 - self.target_fat * 9) / 4
        )

    def target_kcal_for(self, day) -> int:
        """Objetivo calórico de un día concreto, modulado por el patrón de ejercicio."""
        delta = self.active_by_weekday.get(day.weekday(), 0.0)
        return max(MIN_DAILY_KCAL, min(MAX_DAILY_KCAL, round(self.base_daily_kcal + delta)))

    def analyse_adherence(self):
        if not self.food_logs:
            return None
        by_date = defaultdict(list)
        for fl in self.food_logs:
            by_date[fl.date].append(fl)
        results = []
        for d, logs in sorted(by_date.items()):
            totals = {"calories": 0.0, "proteins": 0.0, "lipids": 0.0, "carbs": 0.0}
            for fl in logs:
                t = fl.get_nutritional_totals()
                for k in totals:
                    totals[k] += t.get(k, 0)
            plan = self.plan_for_day(d)
            results.append({
                "date": d,
                "actual": totals,
                "plan": plan["macros"],
                "diff": {k: round(totals.get(k, 0) - plan["macros"].get(k, 0), 1) for k in totals},
            })
        return results

    def _weight_trend(self):
        if len(self.weights) < 3:
            return 0.0
        days = [(w.date - self.weights[0].date).days for w in self.weights]
        vals = [float(w.weight) for w in self.weights]
        slope, _ = _simple_linear_regression(days, vals)
        return slope

    def plan_for_day(self, day=None):
        day = day or date.today()
        kcal = self.target_kcal_for(day)

        breakfast = dict(BREAKFAST_TOTALS)
        dinner = dict(DINNER_TOTALS)

        # Fill remaining kcal with lunch
        remaining = kcal - breakfast["kcal"] - dinner["kcal"]
        lunch = _compute_lunch_macros(kcal, self.current_weight)
        lunch = _adjust_macros_to_kcal(lunch, remaining)

        total = {
            "kcal": breakfast["kcal"] + lunch["kcal"] + dinner["kcal"],
            "protein": breakfast["protein"] + lunch["protein"] + dinner["protein"],
            "fat": breakfast["fat"] + lunch["fat"] + dinner["fat"],
            "carbs": breakfast["carbs"] + lunch["carbs"] + dinner["carbs"],
        }

        bf_pct = round(breakfast["kcal"] / total["kcal"] * 100) if total["kcal"] else 35
        l_pct = round(lunch["kcal"] / total["kcal"] * 100) if total["kcal"] else 47
        d_pct = round(dinner["kcal"] / total["kcal"] * 100) if total["kcal"] else 18

        return {
            "date": day,
            "daily_kcal_target": kcal,
            "daily_kcal_base": self.base_daily_kcal,
            "tdee_estimated": round(self.tdee),
            "exercise_delta": round(self.active_by_weekday.get(day.weekday(), 0.0)),
            "distribution_pct": {"desayuno": bf_pct, "comida": l_pct, "cena": d_pct},
            "macros": total,
            "meals": {
                "desayuno": {
                    "macros": breakfast,
                    "foods": BREAKFAST_TEMPLATE["foods"],
                    "advice": "3 huevos + 60g avena + fruta + 25g frutos secos + yogur",
                },
                "comida": {
                    "macros": lunch,
                    "foods_hint": f"{lunch['protein']}g proteína (pollo/pescado/carne) + {lunch['carbs']}g carbohidratos + verduras + AOVE",
                    "advice": "Prioriza proteína animal, legumbres y verduras de hoja verde.",
                    "protein_range": (150, 200),
                    "carbs_range": (100, 120),
                },
                "cena": {
                    "macros": dinner,
                    "foods": DINNER_TEMPLATE["foods"],
                    "advice": "Batido de caseína + yogur/queso + nueces para recuperación nocturna.",
                },
            },
            "supplements": SUPPLEMENTS,
            "notes": [],
        }

    def get_weekly_plan(self):
        today = date.today()
        plans = []
        for i in range(7):
            d = today + timedelta(days=i)
            plans.append(self.plan_for_day(d))

        # Nota base explicando por qué la IA ajusta el objetivo cada día
        for p in plans:
            if p["exercise_delta"]:
                sign = "+" if p["exercise_delta"] > 0 else ""
                p["notes"].append(
                    f"Objetivo ajustado por ejercicio: tu gasto esperado este día "
                    f"({sign}{p['exercise_delta']} kcal sobre tu media) modula el total a {p['daily_kcal_target']} kcal."
                )

        trend = self._weight_trend()
        if self._weight_trend_has_data():
            weekly_rate = trend * 7.0
            if trend > 0.02:
                for p in plans:
                    p["notes"].append(
                        f"Estás ganando peso (~{weekly_rate:.2f} kg/semana). La IA ha reducido tu consumo a "
                        f"{p['daily_kcal_target']} kcal para girar el balance hacia la pérdida."
                    )
            elif trend > -0.05:
                for p in plans:
                    p["notes"].append(
                        "Tendencia estable. Ajustando el déficit para acercarte a tu objetivo de pérdida semanal."
                    )
            else:
                for p in plans:
                    p["notes"].append(
                        f"Tendencia de pérdida (~{abs(weekly_rate):.2f} kg/semana) alineada o superior al objetivo. Mantén el plan."
                    )
        else:
            for p in plans:
                p["notes"].append(
                    "Sin suficiente historial de peso: la IA parte de tu BMR y gasto por actividad y recalculará al acumular datos."
                )

        adherence = self.analyse_adherence()
        if adherence:
            recent = [a for a in adherence if a["date"] >= date.today() - timedelta(days=7)]
            if recent:
                avg_cal = mean(a["actual"]["calories"] for a in recent)
                avg_target = mean(p["daily_kcal_target"] for p in plans)
                if abs(avg_cal - avg_target) > 150:
                    for p in plans:
                        p["notes"].append(
                            f"Tu ingesta media real es {avg_cal:.0f} kcal. "
                            f"{'Aumenta' if avg_cal < avg_target else 'Reduce'} raciones para ajustarte al objetivo de {avg_target:.0f} kcal."
                        )

        return plans

    def get_ml_insights(self):
        if len(self.weights) < 5 or not self.food_logs:
            return []
        insights = []

        by_date = defaultdict(list)
        for fl in self.food_logs:
            by_date[fl.date].append(fl)

        weight_by_date = {w.date: float(w.weight) for w in self.weights}
        data = []
        for d in sorted(by_date.keys()):
            if d not in weight_by_date:
                continue
            logs = by_date[d]
            totals = {"calories": 0.0, "proteins": 0.0, "lipids": 0.0, "carbs": 0.0}
            for fl in logs:
                t = fl.get_nutritional_totals()
                for k in totals:
                    totals[k] += t.get(k, 0)
            total_cal = totals["calories"]
            if total_cal == 0:
                continue
            p_ratio = totals["proteins"] * 4 / total_cal
            f_ratio = totals["lipids"] * 9 / total_cal
            next_d = d + timedelta(days=1)
            if next_d in weight_by_date:
                w_change = weight_by_date[next_d] - weight_by_date[d]
                data.append((p_ratio, f_ratio, w_change, total_cal))

        if len(data) < 5:
            return []

        protein_ratios = [d[0] for d in data]
        weight_changes = [d[2] for d in data]
        slope, _ = _simple_linear_regression(protein_ratios, weight_changes)
        if slope < -0.01:
            insights.append({
                "type": "success", "icon": "bi-graph-up-arrow",
                "title": "Proteína y Pérdida de Peso",
                "text": "Mayor proporción de proteína se correlaciona con mejor pérdida de peso. Mantén >30% de calorías de proteína.",
            })

        deficits = [d[3] for d in data if d[3] < self.base_daily_kcal]
        changes = [d[2] for d in data if d[3] < self.base_daily_kcal]
        if len(deficits) >= 5:
            slope_d, _ = _simple_linear_regression(deficits, changes)
            if slope_d < 0:
                g_per_500 = abs(slope_d) * 500 * 1000
                insights.append({
                    "type": "info", "icon": "bi-calculator",
                    "title": "Déficit Calórico Personalizado",
                    "text": f"Por cada 500 kcal de déficit, tu peso reduce ~{g_per_500:.0f}g al día siguiente.",
                })

        fat_ratios = [d[1] for d in data]
        slope_f, _ = _simple_linear_regression(fat_ratios, weight_changes)
        if slope_f > 0.005:
            insights.append({
                "type": "warning", "icon": "bi-exclamation-diamond",
                "title": "Vigila las Grasas",
                "text": "Una proporción alta de grasa en la dieta (>35%) se asocia con menor pérdida de peso. Prioriza grasas insaturadas.",
            })

        return insights
