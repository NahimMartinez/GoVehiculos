from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
import re

from .models import Usuario


class UsuarioValidationsMixin:
    nombre_pattern = r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]+$"
    dni_pattern = r"^\d{8}$"

    def clean_first_name(self):
        first_name = self.cleaned_data.get("first_name", "").strip()
        if not re.fullmatch(self.nombre_pattern, first_name):
            raise ValidationError("El nombre solo puede contener letras.")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get("last_name", "").strip()
        if not re.fullmatch(self.nombre_pattern, last_name):
            raise ValidationError("El apellido solo puede contener letras.")
        return last_name

    def clean_dni(self):
        dni = self.cleaned_data.get("dni", "").strip()
        if not re.fullmatch(self.dni_pattern, dni):
            raise ValidationError("El DNI debe contener exactamente 8 números, sin puntos ni espacios.")
        return dni

class RegistroUsuarioForm(UsuarioValidationsMixin, UserCreationForm):
    rol = forms.ChoiceField(choices=[])
    roles_permitidos = ("Clientes", "Socios")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_class = "w-full bg-surface-container-high border-none rounded-lg focus:ring-2 focus:ring-primary"
        placeholders = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "tu@email.com",
            "dni": "Documento",
            "username": "Nombre de usuario",
            "password1": "Crea una contrasena",
            "password2": "Repite la contrasena",
        }

        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", base_class)
            if name in placeholders:
                field.widget.attrs.setdefault("placeholder", placeholders[name])

        self.fields["first_name"].widget.attrs.setdefault("pattern", UsuarioValidationsMixin.nombre_pattern)
        self.fields["last_name"].widget.attrs.setdefault("pattern", UsuarioValidationsMixin.nombre_pattern)
        self.fields["dni"].widget.attrs.setdefault("pattern", UsuarioValidationsMixin.dni_pattern)
        self.fields["dni"].widget.attrs.setdefault("inputmode", "numeric")
        self.fields["dni"].widget.attrs.setdefault("maxlength", "8")

        grupos = Group.objects.filter(name__in=self.roles_permitidos).order_by("name")
        self.fields["rol"].choices = [(grupo.name, grupo.name) for grupo in grupos]

        self.fields["email"].widget.attrs.setdefault("autocomplete", "email")
        self.fields["username"].widget.attrs.setdefault("autocomplete", "username")
        self.fields["password1"].widget.attrs.setdefault("autocomplete", "new-password")
        self.fields["password2"].widget.attrs.setdefault("autocomplete", "new-password")

    class Meta:
        model = Usuario
        # Campos a mostrar en el HTML
        fields = ['email', 'dni','first_name', 'last_name', 'username', 'rol', 'password1', 'password2']

class EditarUsuarioForm(UsuarioValidationsMixin, forms.ModelForm):
    rol = forms.ChoiceField(choices=[])

    class Meta:
        model = Usuario
        fields = ["email", "dni", "first_name", "last_name", "username", "rol"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_class = "w-full bg-surface-container-high border-none rounded-lg focus:ring-2 focus:ring-primary"
        placeholders = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "tu@email.com",
            "dni": "Documento",
            "username": "Nombre de usuario"
        }
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", base_class)
            if name in placeholders:
                field.widget.attrs.setdefault("placeholder", placeholders[name])

        self.fields["first_name"].widget.attrs.setdefault("pattern", UsuarioValidationsMixin.nombre_pattern)
        self.fields["last_name"].widget.attrs.setdefault("pattern", UsuarioValidationsMixin.nombre_pattern)
        self.fields["dni"].widget.attrs.setdefault("pattern", UsuarioValidationsMixin.dni_pattern)
        self.fields["dni"].widget.attrs.setdefault("inputmode", "numeric")
        self.fields["dni"].widget.attrs.setdefault("maxlength", "8")

        grupos = Group.objects.order_by("name")
        self.fields["rol"].choices = [(grupo.name, grupo.name) for grupo in grupos]

        if self.instance and self.instance.pk:
            grupo_actual = self.instance.groups.values_list("name", flat=True).first()
            if grupo_actual:
                self.fields["rol"].initial = grupo_actual