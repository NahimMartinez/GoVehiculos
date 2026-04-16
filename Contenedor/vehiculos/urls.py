from django.urls import path
from . import views

urlpatterns = [
    path('mis-vehiculos/', views.mis_vehiculos_view, name='mis_vehiculos'),
    path('lista-vehiculos/', views.listar_vehiculos_view, name='lista_vehiculos'),
    path('detalle-vehiculo/<int:vehiculo_id>/', views.mostrar_detalle_view, name='detalle_vehiculo')
]