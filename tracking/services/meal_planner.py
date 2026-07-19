from datetime import date, timedelta
from collections import defaultdict
from statistics import mean
from tracking.models import FoodLog, WeightMeasurement

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


def _compute_lunch_macros(kcal_target):
    lunch_kcal = kcal_target * 0.47
    protein_g = 175
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
        thirty_days_ago = date.today() - timedelta(days=30)
        self.food_logs = list(
            FoodLog.objects.filter(user=self.user, date__gte=thirty_days_ago)
            .prefetch_related("items__food", "items__recipe__ingredients__food")
            .order_by("date")
        )
        self.weights = list(
            WeightMeasurement.objects.filter(user=self.user, date__gte=thirty_days_ago)
            .order_by("date")
        )

    def _calibrate(self):
        weight = 70.0
        if self.weights:
            weight = float(self.weights[-1].weight)

        bmr = self.user.calculate_bmr(weight)
        target_loss_kg = float(self.user.target_weekly_loss_kg or 0.5)
        daily_deficit = (target_loss_kg * 7700) / 7.0
        self.daily_kcal = max(TARGET_KCAL_RANGE[0], round(bmr - daily_deficit))

        # Blend with actual average intake from history
        if self.food_logs:
            by_date = defaultdict(list)
            for fl in self.food_logs:
                by_date[fl.date].append(fl)
            actual_calories = [sum(fl.get_total_calories() for fl in logs) for logs in by_date.values()]
            if actual_calories:
                avg_intake = mean(actual_calories)
                self.daily_kcal = round(0.6 * self.daily_kcal + 0.4 * avg_intake)

        self.daily_kcal = max(TARGET_KCAL_RANGE[0], min(TARGET_KCAL_RANGE[1], self.daily_kcal))

        protein_per_kg = 2.0
        self.target_protein = round(protein_per_kg * weight)
        self.target_fat = round(self.daily_kcal * 0.25 / 9)
        self.target_carbs = round((self.daily_kcal - self.target_protein * 4 - self.target_fat * 9) / 4)

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
        kcal = self.daily_kcal

        breakfast = dict(BREAKFAST_TOTALS)
        dinner = dict(DINNER_TOTALS)

        # Fill remaining kcal with lunch
        remaining = kcal - breakfast["kcal"] - dinner["kcal"]
        lunch = _compute_lunch_macros(kcal)
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

        trend = self._weight_trend()
        if trend > 0.1:
            for p in plans:
                p["notes"].append("Estás ganando peso. Reduce 100-150 kcal/día o aumenta actividad.")
        elif trend > -0.05:
            for p in plans:
                p["notes"].append("Tendencia estable. Para perder, asegura déficit de 300-500 kcal/día.")
        else:
            for p in plans:
                p["notes"].append("Tendencia de pérdida adecuada. Mantén el plan.")

        adherence = self.analyse_adherence()
        if adherence:
            recent = [a for a in adherence if a["date"] >= date.today() - timedelta(days=7)]
            if recent:
                avg_cal = mean(a["actual"]["calories"] for a in recent)
                if abs(avg_cal - self.daily_kcal) > 150:
                    for p in plans:
                        p["notes"].append(
                            f"Tu ingesta media real es {avg_cal:.0f} kcal. "
                            f"{'Aumenta' if avg_cal < self.daily_kcal else 'Reduce'} raciones para ajustarte al objetivo."
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

        deficits = [d[3] for d in data if d[3] < self.daily_kcal]
        changes = [d[2] for d in data if d[3] < self.daily_kcal]
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
