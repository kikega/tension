"""Servicio de cálculo y caché nutricional para recetas."""

from decimal import Decimal
from typing import Any, Dict

from recipes.models import Recipe


def _to_decimal(value: float) -> Decimal:
    return Decimal(str(round(float(value or 0.0), 2)))


def calculate_recipe_nutrition_summary(recipe: Recipe) -> Dict[str, Any]:
    """Calcula nutrición total, por ración, por 100 g de plato terminado, CG y alérgenos."""
    totals = recipe.calculate_nutrition()
    servings = max(1, int(recipe.servings or 1))
    total_weight_g = recipe.calculate_total_weight()
    effective_weight_g = recipe.get_effective_weight_g()

    per_serving = {k: round(v / servings, 2) for k, v in totals.items()}
    if effective_weight_g > 0:
        factor_100g = 100.0 / effective_weight_g
        per_100g = {k: round(v * factor_100g, 2) for k, v in totals.items()}
    else:
        per_100g = {k: 0.0 for k in totals}

    cg_data = recipe.calculate_glycemic_load()
    cg_per_serving = round(cg_data["total_cg"] / servings, 2)

    sodium_srv = per_serving.get("sodium_mg", 0.0)
    potassium_srv = per_serving.get("potassium_mg", 0.0)
    na_k_ratio = round(sodium_srv / potassium_srv, 2) if potassium_srv > 0 else None

    return {
        "totals": totals,
        "per_serving": per_serving,
        "per_100g": per_100g,
        "total_weight_g": round(total_weight_g, 2),
        "effective_weight_g": round(effective_weight_g, 2),
        "servings": servings,
        "glycemic_load": cg_data,
        "glycemic_load_per_serving": cg_per_serving,
        "sodium_potassium_ratio": na_k_ratio,
        "is_dash_friendly": sodium_srv <= 500.0,
        "allergens": list(recipe.get_allergens()),
    }


def recalculate_recipe_cache(recipe: Recipe) -> Dict[str, Decimal]:
    """Recalcula y persiste los campos ``cached_*`` de una receta sin disparar señales ``post_save``."""
    summary = calculate_recipe_nutrition_summary(recipe)
    ps = summary["per_serving"]

    updates = {
        "cached_total_weight_g": _to_decimal(summary["total_weight_g"]),
        "cached_kcal_per_serving": _to_decimal(ps.get("energy_kcal", 0.0)),
        "cached_proteins_per_serving": _to_decimal(ps.get("proteins_g", 0.0)),
        "cached_carbs_per_serving": _to_decimal(ps.get("carbohydrates_g", 0.0)),
        "cached_lipids_per_serving": _to_decimal(ps.get("lipids_g", 0.0)),
        "cached_fiber_per_serving": _to_decimal(ps.get("fiber_g", 0.0)),
        "cached_sodium_mg_per_serving": _to_decimal(ps.get("sodium_mg", 0.0)),
        "cached_potassium_mg_per_serving": _to_decimal(ps.get("potassium_mg", 0.0)),
        "cached_glycemic_load_per_serving": _to_decimal(summary["glycemic_load_per_serving"]),
    }

    Recipe.objects.filter(pk=recipe.pk).update(**updates)
    for field, val in updates.items():
        setattr(recipe, field, val)
    return updates
