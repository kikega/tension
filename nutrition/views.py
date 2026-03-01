from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django import forms as dj_forms

from .models import Food, FoodCategory, Recipe, RecipeIngredient
from .forms import FoodForm, RecipeForm


class FoodListView(LoginRequiredMixin, ListView):
    model = Food
    template_name = "nutrition/food_list.html"
    context_object_name = "foods"
    paginate_by = 30

    def get_queryset(self):
        qs = Food.objects.select_related("category").all()
        category = self.request.GET.get("category")
        query = self.request.GET.get("q")
        if category:
            qs = qs.filter(category_id=category)
        if query:
            qs = qs.filter(name__icontains=query)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = FoodCategory.objects.all()
        context["selected_category"] = self.request.GET.get("category", "")
        context["query"] = self.request.GET.get("q", "")
        return context


class FoodCreateView(LoginRequiredMixin, CreateView):
    model = Food
    form_class = FoodForm
    template_name = "nutrition/food_form.html"
    success_url = reverse_lazy("food_list")


class FoodDetailView(LoginRequiredMixin, DetailView):
    model = Food
    template_name = "nutrition/food_detail.html"
    context_object_name = "food"


class RecipeListView(LoginRequiredMixin, ListView):
    model = Recipe
    template_name = "nutrition/recipe_list.html"
    context_object_name = "recipes"
    paginate_by = 20

    def get_queryset(self):
        return Recipe.objects.all()


class RecipeCreateView(LoginRequiredMixin, CreateView):
    model = Recipe
    form_class = RecipeForm
    template_name = "nutrition/recipe_form.html"
    success_url = reverse_lazy("recipe_list")


class RecipeDetailView(LoginRequiredMixin, DetailView):
    model = Recipe
    template_name = "nutrition/recipe_detail.html"
    context_object_name = "recipe"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["nutrition"] = self.object.calculate_nutrition()
        return context
