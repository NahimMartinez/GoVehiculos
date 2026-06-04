from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Datos extra", {"fields": ("dni",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Datos extra", {"fields": ("dni",)}),)
    list_display = ("email", "username", "first_name", "last_name", "is_staff")
    ordering = ("email",)

