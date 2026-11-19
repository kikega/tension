import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest

from .models import Food, FoodCategory
from .forms import FoodForm
from .services.nutrition_calculator import (
    NUTRIENT_FIELDS,
    normalize_nutrients_to_100g,
    scale_nutrients_for_weight,
    calculate_glycemic_load_for_portion,
)


class FoodListView(LoginRequiredMixin, ListView):
    """Lista del catálogo de alimentos (globales + propios del usuario)."""
    model = Food
    template_name = "nutrition/food_list.html"
    context_object_name = "foods"
    paginate_by = 30

    def get_queryset(self):
        qs = Food.objects.filter(
            Q(user__isnull=True) | Q(user=self.request.user)
        ).select_related("category")
        category = self.request.GET.get("category")
        query = self.request.GET.get("q")
        if category:
            qs = qs.filter(category_id=category)
        if query:
            qs = qs.filter(name__icontains=query)
        return qs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["categories"] = FoodCategory.objects.all()
        context["selected_category"] = self.request.GET.get("category", "")
        context["query"] = self.request.GET.get("q", "")
        return context


class FoodCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Alta de alimentos en el catálogo oficial (requiere staff)."""
    model = Food
    form_class = FoodForm
    template_name = "nutrition/food_form.html"
    success_url = reverse_lazy("food_list")

    def test_func(self) -> bool:
        return bool(self.request.user.is_staff)


class FoodDetailView(LoginRequiredMixin, DetailView):
    """Detalle de un alimento del catálogo."""
    model = Food
    template_name = "nutrition/food_detail.html"
    context_object_name = "food"

    def get_queryset(self):
        return Food.objects.filter(
            Q(user__isnull=True) | Q(user=self.request.user)
        )


class FoodUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Edición de alimentos (staff para globales, usuario para sus propios alimentos)."""
    model = Food
    form_class = FoodForm
    template_name = "nutrition/food_form.html"

    def test_func(self) -> bool:
        food = self.get_object()
        if self.request.user.is_staff:
            return True
        return bool(food.user and food.user == self.request.user)

    def get_success_url(self) -> str:
        return reverse_lazy("food_detail", kwargs={"pk": self.object.pk})


class FoodDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Eliminación de alimentos (staff para globales, usuario para sus propios alimentos)."""
    model = Food
    template_name = "nutrition/food_confirm_delete.html"
    success_url = reverse_lazy("food_list")

    def test_func(self) -> bool:
        food = self.get_object()
        if self.request.user.is_staff:
            return True
        return bool(food.user and food.user == self.request.user)


# ==============================================================================
# ENDPOINTS API PARA CREACIÓN Y CONSULTA AL VUELO
# ==============================================================================

class QuickFoodCreateAPIView(LoginRequiredMixin, View):
    """Endpoint AJAX para crear un alimento al vuelo con cálculo proporcional."""

    def post(self, request, *args, **kwargs) -> JsonResponse:
        try:
            if request.content_type == "application/json":
                data = json.loads(request.body.decode("utf-8"))
            else:
                data = request.POST.dict()

            name = (data.get("name") or "").strip()
            if not name:
                return JsonResponse({"success": False, "error": "El nombre del alimento es obligatorio."}, status=400)

            portion_type = data.get("portion_type", "100g")
            portion_weight_str = data.get("portion_weight_g") or "100"
            try:
                portion_weight_g = float(portion_weight_str)
            except (ValueError, TypeError):
                portion_weight_g = 100.0

            category_id = data.get("category")
            category = None
            if category_id:
                try:
                    category = FoodCategory.objects.get(pk=int(category_id))
                except (FoodCategory.DoesNotExist, ValueError):
                    pass

            seasonality = data.get("seasonality", "all")
            description = (data.get("description") or "").strip()

            # Extraer nutrientes
            raw_nutrients: Dict[str, Any] = {}
            for field in NUTRIENT_FIELDS:
                raw_nutrients[field] = data.get(field)
            raw_nutrients["glycemic_index"] = data.get("glycemic_index")

            # Normalizar a 100g si fue ingresado por porción de peso
            if portion_type == "custom_weight" and portion_weight_g > 0 and portion_weight_g != 100.0:
                normalized = normalize_nutrients_to_100g(raw_nutrients, portion_weight_g)
            else:
                normalized = {}
                for field in NUTRIENT_FIELDS:
                    val = raw_nutrients.get(field)
                    if val is not None and str(val).strip() != "":
                        try:
                            normalized[field] = Decimal(str(round(float(val), 2)))
                        except (ValueError, TypeError):
                            normalized[field] = None
                    else:
                        normalized[field] = None
                gi = raw_nutrients.get("glycemic_index")
                if gi is not None and str(gi).strip() != "":
                    try:
                        normalized["glycemic_index"] = Decimal(str(round(float(gi), 2)))
                    except (ValueError, TypeError):
                        normalized["glycemic_index"] = None
                else:
                    normalized["glycemic_index"] = None

            # Crear el alimento asociado al usuario
            food = Food.objects.create(
                user=request.user,
                name=name,
                category=category,
                description=description,
                seasonality=seasonality,
                **normalized
            )

            return JsonResponse({
                "success": True,
                "food": {
                    "id": food.id,
                    "name": food.name,
                    "energy_kcal": float(food.energy_kcal) if food.energy_kcal is not None else 0.0,
                    "proteins_g": float(food.proteins_g) if food.proteins_g is not None else 0.0,
                    "lipids_g": float(food.lipids_g) if food.lipids_g is not None else 0.0,
                    "carbohydrates_g": float(food.carbohydrates_g) if food.carbohydrates_g is not None else 0.0,
                    "fiber_g": float(food.fiber_g) if food.fiber_g is not None else 0.0,
                    "glycemic_index": float(food.glycemic_index) if food.glycemic_index is not None else None,
                },
                "entered_portion_weight_g": portion_weight_g,
                "message": f"Alimento '{food.name}' creado correctamente."
            })

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)


class FoodSearchAPIView(LoginRequiredMixin, View):
    """Endpoint AJAX para buscar y obtener catálogo de alimentos accesibles por el usuario."""

    def get(self, request, *args, **kwargs) -> JsonResponse:
        q = (request.GET.get("q") or "").strip()
        qs = Food.objects.filter(
            Q(user__isnull=True) | Q(user=request.user)
        ).select_related("category").order_by("name")

        if q:
            qs = qs.filter(name__icontains=q)

        foods_data = []
        for food in qs[:1000]:
            foods_data.append({
                "id": food.id,
                "name": food.name,
                "category": food.category.name if food.category else "",
                "energy_kcal": float(food.energy_kcal) if food.energy_kcal is not None else 0.0,
                "proteins_g": float(food.proteins_g) if food.proteins_g is not None else 0.0,
                "lipids_g": float(food.lipids_g) if food.lipids_g is not None else 0.0,
                "carbohydrates_g": float(food.carbohydrates_g) if food.carbohydrates_g is not None else 0.0,
                "fiber_g": float(food.fiber_g) if food.fiber_g is not None else 0.0,
                "glycemic_index": float(food.glycemic_index) if food.glycemic_index is not None else None,
                "is_custom": (food.user_id is not None),
            })

        return JsonResponse({"success": True, "foods": foods_data})
