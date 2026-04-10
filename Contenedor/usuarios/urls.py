from django.urls import path
from . import views

urlpatterns = [
    path('registro/', views.registro_view, name='registro'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('abm_usuarios/', views.abm_usuarios_view, name='abm_usuarios'),
    path('abm_usuarios/editar/<int:usuario_id>/', views.editar_usuario_view, name='editar_usuario'),
]