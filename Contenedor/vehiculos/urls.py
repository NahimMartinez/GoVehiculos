from django.urls import path
from . import views

urlpatterns = [
    path('mis-vehiculos/', views.mis_vehiculos_view, name='mis_vehiculos'),
]