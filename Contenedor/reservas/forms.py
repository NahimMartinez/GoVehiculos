from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
import re
from .models import Reserva
from usuarios.models import Usuario

#ReservarVehiculoForm (ACA CREAR FORMULARIO PARA RESERVAR VEHICULO.) 

