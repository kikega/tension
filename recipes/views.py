import json
from decimal import Decimal
from typing import Any, Dict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from nutrition.models import Food

from .forms import RecipeForm, RecipeIngredientFormSet, RecipeMediaFormSet
from .models import Recipe, RecipeIngredient


class RecipeListView(LoginRequiredMixin, ListView):
    """Listado de recetas accesibles (globales + propias del usuario)."""
    model = Recipe
    template_name = "recipes/recipe_list.html"
    context_object_name = "recipes"
    paginate_by = 20

    def get_queryset(self):
        return Recipe.objects.visible_for(self.request.user).prefetch_related("ingredients", "media")


class RecipeCreateView(LoginRequiredMixin, CreateView):
    """Creación estándar de receta desde la sección de recetas."""
    model = Recipe
    form_class = RecipeForm
    template_name = "recipes/recipe_form.html"
    success_url = reverse_lazy("recipe_list")

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data["ingredients"] = RecipeIngredientFormSet(self.request.POST, form_kwargs={"user": self.request.user})
            data["media_formset"] = RecipeMediaFormSet(self.request.POST, self.request.FILES, prefix="media")
        else:
            data["ingredients"] = RecipeIngredientFormSet(form_kwargs={"user": self.request.user})
            data["media_formset"] = RecipeMediaFormSet(prefix="media")
        
        foods_qs = Food.objects.filter(
            Q(user__isnull=True) | Q(user=self.request.user)
        ).order_by("name")
        data["available_foods"] = [
            {
                "id": f.id,
                "name": f.name,
                "energy_kcal": float(f.energy_kcal or 0),
                "proteins_g": float(f.proteins_g or 0),
                "lipids_g": float(f.lipids_g or 0),
                "carbohydrates_g": float(f.carbohydrates_g or 0),
                "glycemic_index": float(f.glycemic_index) if f.glycemic_index is not None else None,
            }
            for f in foods_qs
        ]
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        ingredients = context["ingredients"]
        media_formset = context["media_formset"]
        if not ingredients.is_valid() or not media_formset.is_valid():
            return self.form_invalid(form)
        with transaction.atomic():
            form.instance.user = self.request.user
            self.object = form.save()
            ingredients.instance = self.object
            ingredients.save()
            media_formset.instance = self.object
            media_formset.save()
        return super().form_valid(form)


class RecipeDetailView(LoginRequiredMixin, DetailView):
    """Vista detallada de una receta con desglose nutricional."""
    model = Recipe
    template_name = "recipes/recipe_detail.html"
    context_object_name = "recipe"

    def get_queryset(self):
        return Recipe.objects.visible_for(self.request.user).prefetch_related("ingredients", "media")

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        nutrition = self.object.calculate_nutrition()
        servings = self.object.servings or 1
        nutrition_per_serving = {
            k: (v / servings) if v is not None else None
            for k, v in nutrition.items()
        }
        context["nutrition"] = nutrition
        context["nutrition_per_serving"] = nutrition_per_serving
        context["glycemic_load"] = self.object.calculate_glycemic_load()
        return context


class RecipeUpdateView(LoginRequiredMixin, UpdateView):
    """Edición de recetas propias."""
    model = Recipe
    form_class = RecipeForm
    template_name = "recipes/recipe_form.html"

    def get_queryset(self):
        return Recipe.objects.editable_by(self.request.user)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data["ingredients"] = RecipeIngredientFormSet(self.request.POST, instance=self.object, form_kwargs={"user": self.request.user})
            data["media_formset"] = RecipeMediaFormSet(self.request.POST, self.request.FILES, instance=self.object, prefix="media")
        else:
            data["ingredients"] = RecipeIngredientFormSet(instance=self.object, form_kwargs={"user": self.request.user})
            data["media_formset"] = RecipeMediaFormSet(instance=self.object, prefix="media")
        
        foods_qs = Food.objects.filter(
            Q(user__isnull=True) | Q(user=self.request.user)
        ).order_by("name")
        data["available_foods"] = [
            {
                "id": f.id,
                "name": f.name,
                "energy_kcal": float(f.energy_kcal or 0),
                "proteins_g": float(f.proteins_g or 0),
                "lipids_g": float(f.lipids_g or 0),
                "carbohydrates_g": float(f.carbohydrates_g or 0),
                "glycemic_index": float(f.glycemic_index) if f.glycemic_index is not None else None,
            }
            for f in foods_qs
        ]
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        ingredients = context["ingredients"]
        media_formset = context["media_formset"]
        if not ingredients.is_valid() or not media_formset.is_valid():
            return self.form_invalid(form)
        with transaction.atomic():
            self.object = form.save()
            ingredients.instance = self.object
            ingredients.save()
            media_formset.instance = self.object
            media_formset.save()
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse_lazy("recipe_detail", kwargs={"pk": self.object.pk})


class RecipeDeleteView(LoginRequiredMixin, DeleteView):
    """Eliminación de recetas propias."""
    model = Recipe
    template_name = "recipes/recipe_confirm_delete.html"
    success_url = reverse_lazy("recipe_list")

    def get_queryset(self):
        return Recipe.objects.editable_by(self.request.user)


# ==============================================================================
# ENDPOINTS API PARA CREACIÓN Y CONSULTA AL VUELO
# ==============================================================================

class QuickRecipeCreateAPIView(LoginRequiredMixin, View):
    """Endpoint AJAX para crear una receta al vuelo con sus ingredientes."""

    def post(self, request, *args, **kwargs) -> JsonResponse:
        try:
            if request.content_type == "application/json":
                data = json.loads(request.body.decode("utf-8"))
            else:
                data = request.POST.dict()
                if "ingredients" in data and isinstance(data["ingredients"], str):
                    try:
                        data["ingredients"] = json.loads(data["ingredients"])
                    except Exception:
                        pass

            name = (data.get("name") or "").strip()
            if not name:
                return JsonResponse({"success": False, "error": "El nombre de la receta es obligatorio."}, status=400)

            servings_str = data.get("servings") or "1"
            try:
                servings = max(1, int(servings_str))
            except (ValueError, TypeError):
                servings = 1

            description = (data.get("description") or "").strip()
            instructions = (data.get("instructions") or "").strip()
            ingredients_list = data.get("ingredients") or []

            if not ingredients_list or not isinstance(ingredients_list, list):
                return JsonResponse({"success": False, "error": "La receta debe tener al menos un ingrediente."}, status=400)

            with transaction.atomic():
                recipe = Recipe.objects.create(
                    user=request.user,
                    name=name,
                    servings=servings,
                    description=description,
                    instructions=instructions,
                )

                created_ingredients_count = 0
                for item in ingredients_list:
                    food_id = item.get("food_id") or item.get("food")
                    quantity_str = item.get("quantity_g")
                    if not food_id or not quantity_str:
                        continue

                    try:
                        quantity_g = Decimal(str(quantity_str))
                        if quantity_g <= 0:
                            continue
                    except Exception:
                        continue

                    food = Food.objects.filter(
                        Q(user__isnull=True) | Q(user=request.user),
                        pk=int(food_id)
                    ).first()

                    if food:
                        RecipeIngredient.objects.create(
                            recipe=recipe,
                            food=food,
                            quantity_g=quantity_g
                        )
                        created_ingredients_count += 1

                if created_ingredients_count == 0:
                    transaction.set_rollback(True)
                    return JsonResponse({"success": False, "error": "No se añadieron ingredientes válidos a la receta."}, status=400)

            total_weight = recipe.calculate_total_weight()
            nutrition = recipe.calculate_nutrition()

            return JsonResponse({
                "success": True,
                "recipe": {
                    "id": recipe.id,
                    "name": recipe.name,
                    "servings": recipe.servings,
                    "total_weight_g": total_weight,
                    "calories": round(nutrition.get("energy_kcal", 0.0), 1),
                    "proteins": round(nutrition.get("proteins_g", 0.0), 1),
                    "lipids": round(nutrition.get("lipids_g", 0.0), 1),
                    "carbs": round(nutrition.get("carbohydrates_g", 0.0), 1),
                },
                "message": f"Receta '{recipe.name}' creada correctamente."
            })

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)


class RecipeDetailAPIView(LoginRequiredMixin, View):
    """Endpoint AJAX para obtener los detalles e ingredientes de una receta para usar como plantilla."""

    def get(self, request, pk: int, *args, **kwargs) -> JsonResponse:
        recipe = Recipe.objects.visible_for(request.user).filter(pk=pk).first()

        if not recipe:
            return JsonResponse({"success": False, "error": "Receta no encontrada."}, status=404)

        ingredients_data = []
        for ing in recipe.ingredients.select_related("food").all():
            ingredients_data.append({
                "food_id": ing.food.id,
                "food_name": ing.food.name,
                "quantity_g": float(ing.quantity_g),
                "energy_kcal": float(ing.food.energy_kcal or 0),
                "proteins_g": float(ing.food.proteins_g or 0),
                "lipids_g": float(ing.food.lipids_g or 0),
                "carbohydrates_g": float(ing.food.carbohydrates_g or 0),
                "glycemic_index": float(ing.food.glycemic_index) if ing.food.glycemic_index is not None else None,
            })

        nutrition = recipe.calculate_nutrition()
        cg_data = recipe.calculate_glycemic_load()

        return JsonResponse({
            "success": True,
            "recipe": {
                "id": recipe.id,
                "name": recipe.name,
                "description": recipe.description,
                "instructions": recipe.instructions,
                "servings": recipe.servings,
                "total_weight_g": recipe.calculate_total_weight(),
                "ingredients": ingredients_data,
                "nutrition": {
                    "energy_kcal": round(nutrition.get("energy_kcal", 0.0), 1),
                    "proteins_g": round(nutrition.get("proteins_g", 0.0), 1),
                    "lipids_g": round(nutrition.get("lipids_g", 0.0), 1),
                    "carbohydrates_g": round(nutrition.get("carbohydrates_g", 0.0), 1),
                },
                "glycemic_load": cg_data,
            }
        })
