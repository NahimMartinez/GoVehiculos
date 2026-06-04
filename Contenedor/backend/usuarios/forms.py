from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
import re
from .models import Usuario


class UsuarioValidationsMixin:
    """Mixin con validaciones reutilizables para formularios de usuario.
    
    Centraliza reglas de validación para nombre, apellido y DNI para evitar
    duplicar lógica entre los formularios de registro y edición.
    
    """
    nombre_pattern = r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]+$"
    dni_pattern = r"^\d{8}$"

    def clean_first_name(self):
        """Valida que el nombre contenga solo letras y espacios."""
        # Normalizar el valor eliminado espacios externos
        first_name = self.cleaned_data.get("first_name", "").strip()
        # Verificar que el texto cumpla con el patrón permitido
        if not re.fullmatch(self.nombre_pattern, first_name):
            raise ValidationError("El nombre solo puede contener letras.")
        # Devolver el valor limpio para que siga el flujo normal del formulario
        return first_name

    def clean_last_name(self):
        """Valida que el apellido contenga solo letras y espacios."""
        # Normalizar el valor eliminado espacios externos
        last_name = self.cleaned_data.get("last_name", "").strip()
        # Verificar que el texto cumpla con el patrón permitido
        if not re.fullmatch(self.nombre_pattern, last_name):
            raise ValidationError("El apellido solo puede contener letras.")
        # Devolver el valor limpio para que siga el flujo normal del formulario
        return last_name

    def clean_dni(self):
        """Valida que el DNI tenga exactamente ocho números."""
        # Normalizar el valor eliminado espacios externos
        dni = self.cleaned_data.get("dni", "").strip()
        # Verificar que el documento tenga el formato esperado
        if not re.fullmatch(self.dni_pattern, dni):
            raise ValidationError("El DNI debe contener exactamente 8 números, sin puntos ni espacios.")
        # Devolver el valor limpio para que siga el flujo normal del formulario
        return dni

class RegistroUsuarioForm(UsuarioValidationsMixin, UserCreationForm):
    """Formulario para registro de nuevos usuarios.
    
    Permite seleccionar rol (Clientes, Socios, Administradores si el usuario logueado es admin).
    """
    rol = forms.ChoiceField(choices=[])

    def __init__(self, *args, usuario_logueado=None, **kwargs):
        """Inicializa el formulario de registro y configura campos visuales y permisos.
        
        Ajusta estilos, placeholders, validaciones del navegador y opciones de rol
        disponibles según el usuario que está autenticado.
        
        """
        super().__init__(*args, **kwargs)
        # Clase base compartida por todos los campos para unificar la apariencia
        base_class = "w-full bg-surface-container-high border-none rounded-lg focus:ring-2 focus:ring-primary"
        # Placeholders para orientar al usuario en el llenado del formulario
        placeholders = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "tu@email.com",
            "dni": "Documento",
            "username": "Nombre de usuario",
            "password1": "Crea una contrasena",
            "password2": "Repite la contrasena",
        }

        # Recorrer los campos y aplicar estilo base y placeholders cuando corresponda
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", base_class)
            if name in placeholders:
                field.widget.attrs.setdefault("placeholder", placeholders[name])

        # Agregar restricciones de entrada para validación en el navegador
        self.fields["first_name"].widget.attrs.setdefault("pattern", UsuarioValidationsMixin.nombre_pattern)
        self.fields["last_name"].widget.attrs.setdefault("pattern", UsuarioValidationsMixin.nombre_pattern)
        self.fields["dni"].widget.attrs.setdefault("pattern", UsuarioValidationsMixin.dni_pattern)
        self.fields["dni"].widget.attrs.setdefault("inputmode", "numeric")
        self.fields["dni"].widget.attrs.setdefault("maxlength", "8")

        # Determinar roles permitidos segun si el usuario es administrador
        roles_permitidos = ["Clientes", "Socios"]
        if usuario_logueado and usuario_logueado.groups.filter(name="Administradores").exists():
            roles_permitidos.append("Administradores")
        
        # Cargar solo los grupos habilitados para el usuario actual
        grupos = Group.objects.filter(name__in=roles_permitidos).order_by("name")
        # Convertir grupos en opciones para el campo de selección
        self.fields["rol"].choices = [(grupo.name, grupo.name) for grupo in grupos]

        # Configurar atributos de autocompletado para mejorar la experiencia de uso
        self.fields["email"].widget.attrs.setdefault("autocomplete", "email")
        self.fields["username"].widget.attrs.setdefault("autocomplete", "username")
        self.fields["password1"].widget.attrs.setdefault("autocomplete", "new-password")
        self.fields["password2"].widget.attrs.setdefault("autocomplete", "new-password")

    class Meta:
        model = Usuario
        # Campos a mostrar en el HTML
        fields = ['email', 'dni','first_name', 'last_name', 'username', 'rol', 'password1', 'password2']

class EditarUsuarioForm(UsuarioValidationsMixin, forms.ModelForm):
    """Formulario para editar datos y rol de un usuario existente.
    
    Solo permite asignar rol Administrador si el usuario que edita pertenece
    al grupo Administradores.
    """
    rol = forms.ChoiceField(choices=[])

    class Meta:
        model = Usuario
        fields = ["email", "dni", "first_name", "last_name", "username", "rol"]

    def __init__(self, *args, usuario_logueado=None, **kwargs):
        """Inicializa el formulario de edición y configura campos y permisos.
        
        Aplica estilos, placeholders, restricciones de entrada y define qué grupos
        pueden asignarse según el rol del usuario autenticado.
        
        """
        super().__init__(*args, **kwargs)
        # Clase base compartida por todos los campos para mantener coherencia visual
        base_class = "w-full bg-surface-container-high border-none rounded-lg focus:ring-2 focus:ring-primary"
        # Placeholders para orientar el completado del formulario
        placeholders = {
            "first_name": "Nombre",
            "last_name": "Apellido",
            "email": "tu@email.com",
            "dni": "Documento",
            "username": "Nombre de usuario"
        }
        # Aplicar clase base y placeholders campo por campo
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", base_class)
            if name in placeholders:
                field.widget.attrs.setdefault("placeholder", placeholders[name])

        # Reglas para validación en el navegador
        self.fields["first_name"].widget.attrs.setdefault("pattern", UsuarioValidationsMixin.nombre_pattern)
        self.fields["last_name"].widget.attrs.setdefault("pattern", UsuarioValidationsMixin.nombre_pattern)
        self.fields["dni"].widget.attrs.setdefault("pattern", UsuarioValidationsMixin.dni_pattern)
        self.fields["dni"].widget.attrs.setdefault("inputmode", "numeric")
        self.fields["dni"].widget.attrs.setdefault("maxlength", "8")

        # Determinar grupos disponibles segun permisos del usuario logueado
        if usuario_logueado and usuario_logueado.groups.filter(name="Administradores").exists():
            # Admin puede ver y asignar todos los grupos
            grupos = Group.objects.order_by("name")
        else:
            # No admin solo puede ver Clientes y Socios
            grupos = Group.objects.filter(name__in=["Clientes", "Socios"]).order_by("name")
        
        # Convertir los grupos a opciones del campo de rol
        self.fields["rol"].choices = [(grupo.name, grupo.name) for grupo in grupos]

        # Si el formulario está asociado a una instancia existente, precargar el rol actual
        if self.instance and self.instance.pk:
            grupo_actual = self.instance.groups.values_list("name", flat=True).first()
            if grupo_actual:
                self.fields["rol"].initial = grupo_actual