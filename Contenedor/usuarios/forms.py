from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Usuario

class RegistroUsuarioForm(UserCreationForm):
    OPCIONES_ROL = [('cliente', 'Cliente'), ('socio', 'Socio')]
    rol = forms.ChoiceField(choices=OPCIONES_ROL)

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

        self.fields["email"].widget.attrs.setdefault("autocomplete", "email")
        self.fields["username"].widget.attrs.setdefault("autocomplete", "username")
        self.fields["password1"].widget.attrs.setdefault("autocomplete", "new-password")
        self.fields["password2"].widget.attrs.setdefault("autocomplete", "new-password")

    class Meta:
        model = Usuario
        # Campos a mostrar en el HTML
        fields = ['email', 'dni','first_name', 'last_name', 'username', 'rol', 'password1', 'password2']

