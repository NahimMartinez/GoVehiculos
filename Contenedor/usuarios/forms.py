from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Usuario

class RegistroUsuarioForm(UserCreationForm):
    OPCIONES_ROL = [('cliente', 'Cliente'), ('socio', 'Socio')]
    rol = forms.ChoiceField(choices=OPCIONES_ROL)

    class Meta:
        model = Usuario
        # Campos a mostrar en el HTML
        fields = ['email', 'dni', 'username', 'rol']

