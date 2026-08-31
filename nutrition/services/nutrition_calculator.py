"""Servicio de cálculo y normalización nutricional.

Proporciona funciones puras para calcular, escalar y normalizar valores
nutricionales de alimentos y recetas según el peso o las raciones consumidas.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

# Lista completa de campos de nutrientes disponibles en el modelo Food
NUTRIENT_FIELDS: List[str] = [
    "energy_kcal",
    "proteins_g",
    "lipids_g",
    "cholesterol_mg",
    "carbohydrates_g",
    "fiber_g",
    "water_g",
    "calcium_mg",
    "iron_mg",
    "iodine_ug",
    "magnesium_mg",
    "zinc_mg",
    "sodium_mg",
    "potassium_mg",
    "phosphorus_mg",
    "selenium_ug",
    "thiamine_mg",
    "riboflavin_mg",
    "vitamin_b6_mg",
    "folate_ug",
    "vitamin_b12_ug",
    "vitamin_c_mg",
    "vitamin_a_ug",
    "vitamin_d_ug",
    "vitamin_e_mg",
]


def normalize_nutrients_to_100g(
    raw_nutrients: Dict[str, Any],
    portion_weight_g: Union[float, Decimal, int],
) -> Dict[str, Optional[Decimal]]:
    """Normaliza los valores de nutrientes especificados para una porción al equivalente estándar por 100g.

    Args:
        raw_nutrients: Diccionario con nombres de campos y sus valores brutos.
        portion_weight_g: Peso de la porción en gramos (> 0).

    Returns:
        Diccionario con los valores recalculados para 100g en Decimal (redondeados a 2 decimales).
    """
    weight = float(portion_weight_g)
    if weight <= 0:
        raise ValueError("El peso de la porción debe ser mayor que 0 gramos.")

    factor = 100.0 / weight
    normalized: Dict[str, Optional[Decimal]] = {}

    for field in NUTRIENT_FIELDS:
        val = raw_nutrients.get(field)
        if val is not None and str(val).strip() != "":
            try:
                num_val = float(val)
                scaled = num_val * factor
                normalized[field] = Decimal(str(round(scaled, 2)))
            except (ValueError, TypeError):
                normalized[field] = None
        else:
            normalized[field] = None

    # Índice glucémico se preserva sin escalar si existe
    gi = raw_nutrients.get("glycemic_index")
    if gi is not None and str(gi).strip() != "":
        try:
            normalized["glycemic_index"] = Decimal(str(round(float(gi), 2)))
        except (ValueError, TypeError):
            normalized["glycemic_index"] = None
    else:
        normalized["glycemic_index"] = None

    return normalized


def scale_nutrients_for_weight(
    base_nutrients_100g: Dict[str, Any],
    target_weight_g: Union[float, Decimal, int],
) -> Dict[str, Optional[float]]:
    """Escala los nutrientes de una base de 100g al peso consumido objetivo.

    Args:
        base_nutrients_100g: Diccionario con valores nutricionales por 100g.
        target_weight_g: Peso objetivo en gramos.

    Returns:
        Diccionario con valores nutricionales escalados al peso objetivo.
    """
    weight = float(target_weight_g)
    if weight < 0:
        weight = 0.0

    factor = weight / 100.0
    scaled: Dict[str, Optional[float]] = {}

    for field in NUTRIENT_FIELDS:
        val = base_nutrients_100g.get(field)
        if val is not None and str(val).strip() != "":
            try:
                scaled[field] = round(float(val) * factor, 2)
            except (ValueError, TypeError):
                scaled[field] = None
        else:
            scaled[field] = None

    return scaled


def calculate_glycemic_load_for_portion(
    carbs_g: Optional[Union[float, Decimal]],
    glycemic_index: Optional[Union[float, Decimal]],
) -> Dict[str, Any]:
    """Calcula la carga glucémica (CG) de una porción con carbohidratos.

    Fórmula: CG = (IG * Carbohidratos_porción_g) / 100

    Args:
        carbs_g: Carbohidratos en gramos para la porción consumida.
        glycemic_index: Índice glucémico del alimento (0-100).

    Returns:
        Diccionario con 'cg' (float) y 'has_missing_ig' (bool).
    """
    if carbs_g is None or float(carbs_g) <= 0:
        return {"cg": 0.0, "has_missing_ig": False}

    if glycemic_index is None:
        return {"cg": 0.0, "has_missing_ig": True}

    cg = (float(glycemic_index) * float(carbs_g)) / 100.0
    return {"cg": round(cg, 2), "has_missing_ig": False}
