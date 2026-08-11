from __future__ import annotations

from datetime import date, timedelta
from collections import defaultdict
from statistics import mean
import math
from tracking.models import FoodLog, WeightMeasurement, DailyActivityLog

# ── Fixed recommendations ────────────────────────────────────────────────────
# Nutritional values are totals for the specified serving (NOT per 100g)

BREAKFAST_TEMPLATE = {
    "name": "Desayuno",
    "target_pct": (0.35, 0.40),
    "foods": [
        # Proteína como alimento principal del desayuno (AMIX o AMIX Predator)
        {"name": "AMIX / AMIX Predator (proteína)", "qty_str": "1-2 cacitos (30-60 g)", "protein": 39, "fat": 3, "carbs": 12, "kcal": 230},
        # Café de desayuno: máximo 2 raciones
        {"name": "Café de desayuno", "qty_str": "máx. 2 raciones", "protein": 0, "fat": 0, "carbs": 0, "kcal": 0},
        # El resto variable: fruta al gusto (arándanos, manzana, etc.)
        {"name": "Fruta (arándanos, manzana…)", "qty_str": "al gusto (1-2 piezas)", "protein": 2, "fat": 0, "carbs": 25, "kcal": 100},
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


def _meal_slot(meal_type: str) -> str:
    """Clasifica una etiqueta de comida (libre en la app) en desayuno/comida/cena."""
    t = (meal_type or "").lower()
    if any(k in t for k in ("desayuno", "breakfast", "yogur", "avena")):
        return "desayuno"
    if any(k in t for k in ("cena", "dinner")):
        return "cena"
    return "comida"


def _recipe_macros(recipe) -> dict:
    """Macros totales de una receta sin consultas extra (usa la caché prefetch)."""
    totals = {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for ing in recipe.ingredients.all():
        f = ing.food
        factor = float(ing.quantity_g or 0) / 100.0
        totals["kcal"] += float(f.energy_kcal or 0) * factor
        totals["protein"] += float(f.proteins_g or 0) * factor
        totals["fat"] += float(f.lipids_g or 0) * factor
        totals["carbs"] += float(f.carbohydrates_g or 0) * factor
    return totals


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
        # Ventana de aprendizaje amplia: el algoritmo recuerda más y pondera
        # lo reciente, afinando sus recomendaciones con el tiempo.
        learning_start = date.today() - timedelta(days=120)
        self.food_logs = list(
            FoodLog.objects.filter(user=self.user, date__gte=learning_start)
            .prefetch_related("items__food", "items__recipe__ingredients__food")
            .order_by("date")
        )
        self.weights = list(
            WeightMeasurement.objects.filter(user=self.user, date__gte=learning_start)
            .order_by("date")
        )
        self.daily_activity = list(
            DailyActivityLog.objects.filter(user=self.user, date__gte=learning_start)
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

        self._build_food_preferences()

    def _recency_weight(self, days_ago: int, half_life_days: float = 21.0) -> float:
        """Decaimiento exponencial: lo reciente pesa más, lo antiguo se olvida
        gradualmente. Es lo que permite que el modelo 'aprenda con el tiempo'."""
        return math.exp(-math.log(2) * days_ago / half_life_days)

    def _item_to_nutrition(self, item) -> dict | None:
        """Convierte un ítem (alimento o receta) en su clave canónica + macros."""
        if item.food and item.quantity_g:
            food = item.food
            qty = float(item.quantity_g)
            kcal100 = float(food.energy_kcal or 0)
            if kcal100 <= 0 or qty <= 0:
                return None
            factor = qty / 100.0
            return {
                "key": ("food", food.id),
                "name": food.name,
                "kind": "food",
                "unit": "g",
                "qty": qty,
                "kcal": kcal100 * factor,
                "protein": float(food.proteins_g or 0) * factor,
                "fat": float(food.lipids_g or 0) * factor,
                "carbs": float(food.carbohydrates_g or 0) * factor,
            }
        if item.recipe and item.recipe_id:
            factor = item.calculate_recipe_factor()
            if factor:
                macros = _recipe_macros(item.recipe)
                servings = float(item.recipe.servings or 1)
                scaled = {k: macros[k] * factor for k in macros}
                return {
                    "key": ("recipe", item.recipe_id),
                    "name": item.recipe.name,
                    "kind": "recipe",
                    "unit": "ración",
                    "qty": factor,
                    "kcal": scaled["kcal"],
                    "protein": scaled["protein"],
                    "fat": scaled["fat"],
                    "carbs": scaled["carbs"],
                }
        return None

    def _build_food_preferences(self):
        """Aprendizaje de patrones de comida.

        En lugar de contar alimentos sueltos, detecta la *combinación* habitual
        de cada ingesta (p. ej. el desayuno de siempre) ponderando por recencia,
        descarta las comidas 'fuera de casa' (desviaciones) y mide la estabilidad
        de cada franja: si el desayuno/cena se repiten casi igual se recomienda
        esa rutina; la comida (más variable) se construye con los alimentos más
        frecuentes."""

        today = date.today()

        # Recopilar registros: fecha -> franja -> items (con macros y recencia)
        days_by_slot = {s: {} for s in ("desayuno", "comida", "cena")}
        eaten_out_by_slot = {"desayuno": 0, "comida": 0, "cena": 0}
        for fl in self.food_logs:
            slot = _meal_slot(fl.meal_type)
            if fl.eaten_out:
                eaten_out_by_slot[slot] += 1
                continue
            days_ago = (today - fl.date).days
            weight = self._recency_weight(days_ago)
            items = []
            for item in fl.items.select_related("food", "recipe").all():
                nutr = self._item_to_nutrition(item)
                if nutr:
                    items.append(nutr)
            if not items:
                continue
            days_by_slot[slot].setdefault(fl.date, []).append({"weight": weight, "items": items})

        self.pref_summary = {"desayuno": [], "comida": [], "cena": []}
        self.slot_stats = {}

        for slot in ("desayuno", "comida", "cena"):
            day_records = days_by_slot[slot]
            n_days = len(day_records)
            n_eaten_out = eaten_out_by_slot[slot]
            stats = {
                "n_days": n_days,
                "n_eaten_out": n_eaten_out,
                "stability": 0.0,
                "dominant_combo": None,
                "n_distinct_combos": 0,
            }
            self.slot_stats[slot] = stats
            if n_days == 0:
                continue

            # Firmas de combinación por día (conjunto de claves canónicas)
            combo_weight = defaultdict(float)
            per_combo_items = {}
            for day, entries in day_records.items():
                day_items = []
                for e in entries:
                    day_items.extend(e["items"])
                weight = max(e["weight"] for e in entries)
                all_keys = frozenset(i["key"] for i in day_items)
                combo_weight[all_keys] += weight
                per_combo_items.setdefault(all_keys, []).append(day_items)

            # Combinación dominante y estabilidad (fracción ponderada que la usa)
            dominant_keys, dominant_weight = max(combo_weight.items(), key=lambda kv: kv[1])
            total_weight = sum(combo_weight.values())
            stability = dominant_weight / total_weight if total_weight else 0.0
            stats["n_distinct_combos"] = len(combo_weight)
            stats["stability"] = round(stability, 3)
            stats["dominant_combo"] = dominant_keys

            # Cantidades medias de cada alimento dentro de la combinación dominante
            qty_accum = defaultdict(float)
            qty_count = defaultdict(int)
            distinct_days = defaultdict(float)
            macro_accum = defaultdict(lambda: {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0})
            for day_idx, day_items in enumerate(per_combo_items[dominant_keys]):
                seen_keys = set()
                for i in day_items:
                    qty_accum[i["key"]] += i["qty"]
                    qty_count[i["key"]] += 1
                    for k in macro_accum[i["key"]]:
                        macro_accum[i["key"]][k] += i[k]
                    if i["key"] not in seen_keys:
                        seen_keys.add(i["key"])
                        distinct_days[i["key"]] += day_idx + 1
            combo_foods = []
            meta = {}
            for day_items in per_combo_items[dominant_keys]:
                for i in day_items:
                    meta.setdefault(i["key"], {"name": i["name"], "kind": i["kind"], "unit": i["unit"]})
            for key, m in meta.items():
                n = qty_count.get(key, 0)
                if not n:
                    continue
                avg = {k: macro_accum[key][k] / n for k in macro_accum[key]}
                combo_foods.append({
                    "kind": m["kind"],
                    "name": m["name"],
                    "unit": m["unit"],
                    "qty": qty_accum[key] / n,
                    "kcal": avg["kcal"],
                    "protein": avg["protein"],
                    "fat": avg["fat"],
                    "carbs": avg["carbs"],
                    "count": len(per_combo_items[dominant_keys]),
                    "recency": distinct_days[key],
                })
            combo_foods.sort(key=lambda f: -f["recency"])

            # Lista de honor por frecuencia ponderada para franjas variables
            freq_accum = defaultdict(float)
            freq_count = defaultdict(int)
            freq_qty_accum = defaultdict(float)
            freq_macros = defaultdict(lambda: {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0})
            freq_meta = {}
            for day, entries in day_records.items():
                for e in entries:
                    for i in e["items"]:
                        freq_accum[i["key"]] += e["weight"]
                        freq_count[i["key"]] += 1
                        freq_qty_accum[i["key"]] += i["qty"]
                        for k in freq_macros[i["key"]]:
                            freq_macros[i["key"]][k] += i[k] * e["weight"]
                        freq_meta.setdefault(i["key"], {"name": i["name"], "kind": i["kind"], "unit": i["unit"]})

            freq_foods = []
            for key, m in freq_meta.items():
                n = freq_count.get(key, 0)
                if not n:
                    continue
                avg = {k: freq_macros[key][k] / freq_accum[key] for k in freq_macros[key]}
                freq_foods.append({
                    "kind": m["kind"],
                    "name": m["name"],
                    "unit": m["unit"],
                    "qty": freq_qty_accum[key] / n,
                    "count": freq_accum[key],
                    "kcal": avg["kcal"],
                    "protein": avg["protein"],
                    "fat": avg["fat"],
                    "carbs": avg["carbs"],
                })
            freq_foods.sort(key=lambda f: -f["count"])

            # Si la franja es estable (rutina repetida) se prioriza la combinación
            # dominante; si no, la de alimentos más frecuentes.
            if stability >= 0.45 and combo_foods:
                self.pref_summary[slot] = combo_foods[:8]
            else:
                self.pref_summary[slot] = freq_foods[:8]

    def _build_meal_from_preferences(self, slot, target_kcal=None, natural=False, target_protein=None, target_carbs=None):
        """Construye una comida a partir de los alimentos que el usuario suele
        tomar.

        - natural=True: devuelve la rutina con sus raciones reales (sin escalar),
          para franjas estables como desayuno/cena.
        - natural=False: escala el conjunto hasta alcanzar target_kcal, útil para
          la comida (franja variable) y para llenar la energía restante."""
        candidates = [f for f in self.pref_summary.get(slot, []) if f["kcal"] > 0]
        if not candidates:
            return None

        # Combinación base: los alimentos más frecuentes del usuario
        picked = []
        raw_total = {"kcal": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
        for c in candidates:
            if len(picked) >= 4:
                break
            picked.append(c)
            for k in raw_total:
                raw_total[k] += c[k]
        if raw_total["kcal"] <= 0:
            return None

        if natural or not target_kcal:
            factor = 1.0
            meal_kcal = round(raw_total["kcal"])
        else:
            factor = target_kcal / raw_total["kcal"]
            meal_kcal = target_kcal

        foods = []
        for c in picked:
            qty = c["qty"] * factor
            foods.append({
                "name": c["name"],
                "qty_str": f"{round(qty)} {c['unit']}",
                "qty": round(qty),
                "unit": c["unit"],
                "protein": round(c["protein"] * factor),
                "fat": round(c["fat"] * factor),
                "carbs": round(c["carbs"] * factor),
                "kcal": round(c["kcal"] * factor),
            })

        meal_macros = _sum_foods(foods)
        return {
            "macros": meal_macros,
            "foods": foods,
            "from_preferences": True,
            "count": sum(c["count"] for c in picked),
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
        stats = self.slot_stats

        # Franjas estables (desayuno/cena = rutina): se mantienen con sus raciones
        # reales; la comida (variable) absorbe la energía restante.
        def _natural_or_template(slot, stable, template_totals, template_foods):
            if stable:
                pref = self._build_meal_from_preferences(slot, natural=True)
                if pref:
                    return pref["macros"], pref["foods"], pref
            return dict(template_totals), list(template_foods), None

        bf_pref = None
        d_pref = None
        l_pref = None
        breakfast, breakfast_foods, bf_pref = _natural_or_template(
            "desayuno", stats["desayuno"]["stability"] >= 0.45, BREAKFAST_TOTALS, BREAKFAST_TEMPLATE["foods"])
        dinner, dinner_foods, d_pref = _natural_or_template(
            "cena", stats["cena"]["stability"] >= 0.45, DINNER_TOTALS, DINNER_TEMPLATE["foods"])

        # La comida rellena la energía restante, con un mínimo razonable.
        min_lunch = 400
        remaining = kcal - breakfast["kcal"] - dinner["kcal"]
        if remaining < min_lunch and (breakfast["kcal"] + dinner["kcal"]) > 0:
            scale = max(0.0, (kcal - min_lunch) / (breakfast["kcal"] + dinner["kcal"]))
            breakfast = {k: round(breakfast[k] * scale) for k in breakfast}
            dinner = {k: round(dinner[k] * scale) for k in dinner}
            breakfast_foods = [
                {**f, "protein": round(f["protein"] * scale), "fat": round(f["fat"] * scale),
                 "carbs": round(f["carbs"] * scale), "kcal": round(f["kcal"] * scale),
                 "qty": round(f.get("qty", 0) * scale), "unit": f.get("unit", "")}
                for f in breakfast_foods
            ]
            dinner_foods = [
                {**f, "protein": round(f["protein"] * scale), "fat": round(f["fat"] * scale),
                 "carbs": round(f["carbs"] * scale), "kcal": round(f["kcal"] * scale),
                 "qty": round(f.get("qty", 0) * scale), "unit": f.get("unit", "")}
                for f in dinner_foods
            ]
            for f in breakfast_foods + dinner_foods:
                f["qty_str"] = f"{f.get('qty', f.get('qty_str', ''))} {f.get('unit', '')}".strip()
            remaining = kcal - breakfast["kcal"] - dinner["kcal"]

        l_kcal = max(min_lunch, remaining)

        # La comida variable: compone con los alimentos más frecuentes escalados
        # a la energía restante; si no hay historial, plantilla de macros.
        if stats["comida"]["n_days"] > 0:
            l_pref = self._build_meal_from_preferences("comida", target_kcal=l_kcal)
        if l_pref:
            lunch = l_pref["macros"]
            lunch_foods_hint = " · ".join(f"{f['name']} {f['qty_str']}" for f in l_pref["foods"][:4])
        else:
            lunch = _compute_lunch_macros(kcal, self.current_weight)
            lunch = _adjust_macros_to_kcal(lunch, l_kcal)
            lunch_foods_hint = f"{lunch['protein']}g proteína (pollo/pescado/carne) + {lunch['carbs']}g carbohidratos + verduras + AOVE"

        # Textos
        if bf_pref:
            breakfast_advice = (
                f"El modelo detecta tu desayuno habitual: repites esta combinación en el "
                f"{stats['desayuno']['stability']*100:.0f}% de tus días ({stats['desayuno']['n_days']} días), "
                f"así que la mantiene con tu ración real."
            )
        else:
            breakfast_advice = "Proteína como base (1-2 cacitos de AMIX/AMIX Predator) + café de desayuno (máx. 2 raciones) + fruta al gusto (arándanos, manzana…)."

        if stats["comida"]["stability"] < 0.45 and stats["comida"]["n_days"] > 3:
            lunch_advice = (
                f"Tu comida es la franja más variable (no repites combinación), por eso la "
                f"IA la compone cada día con tus alimentos más frecuentes ajustados a {l_kcal} kcal."
            )
        elif l_pref:
            lunch_advice = (
                f"Basado en tus comidas habituales, ajustado a {l_kcal} kcal y tus macronutrientes objetivo."
            )
        else:
            lunch_advice = "Prioriza proteína animal, legumbres y verduras de hoja verde."

        if d_pref:
            dinner_advice = (
                f"El modelo detecta tu cena habitual: la repites en el "
                f"{stats['cena']['stability']*100:.0f}% de tus días ({stats['cena']['n_days']} días), "
                f"así que la mantiene con tu ración real."
            )
        else:
            dinner_advice = "Batido de caseína + yogur/queso + nueces para recuperación nocturna."

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
                    "foods": breakfast_foods,
                    "advice": breakfast_advice,
                },
                "comida": {
                    "macros": lunch,
                    "foods_hint": lunch_foods_hint,
                    "advice": lunch_advice,
                    "protein_range": (150, 200),
                    "carbs_range": (100, 120),
                },
                "cena": {
                    "macros": dinner,
                    "foods": dinner_foods,
                    "advice": dinner_advice,
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

        # Nota de aprendizaje: estabilidad de cada franja detectada por el modelo
        learning_notes = []
        slot_labels = {"desayuno": "Desayuno", "comida": "Comida", "cena": "Cena"}
        for slot in ("desayuno", "comida", "cena"):
            st = self.slot_stats.get(slot, {})
            n = st.get("n_days", 0)
            if n < 2:
                continue
            stab = st.get("stability", 0.0)
            if stab >= 0.45:
                learning_notes.append(
                    f"{slot_labels[slot]}: has repetido casi la misma ingesta el {stab*100:.0f}% de tus {n} días. "
                    f"El modelo la considera tu rutina y la mantiene estable."
                )
            else:
                learning_notes.append(
                    f"{slot_labels[slot]}: franja variable ({st.get('n_distinct_combos', 0)} combinaciones en {n} días). "
                    f"La IA recomienda variar tus alimentos más frecuentes para mantenerla flexible."
                )
        eaten_out_total = sum(
            self.slot_stats.get(s, {}).get("n_eaten_out", 0) for s in ("desayuno", "comida", "cena")
        )
        if eaten_out_total:
            learning_notes.append(
                f"Se descartaron {eaten_out_total} comidas fuera de casa del aprendizaje del patrón "
                f"habitual, ya que se consideran desviaciones (no tu rutina real)."
            )
        if learning_notes:
            for p in plans:
                p["notes"].extend(learning_notes)

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
