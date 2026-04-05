from django.contrib import admin
# Importamos los modelos que vamos a registrar en el panel de administración de Django
from .models import TipoUsuario, Usuario
# Register your models here.

# Registramos los modelos para que sean visibles en el panel de administración de Django
admin.site.register(TipoUsuario)
admin.site.register(Usuario)

