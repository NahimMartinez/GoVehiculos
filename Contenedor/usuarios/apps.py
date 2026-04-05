from django.apps import AppConfig

# Definimos la configuración de la aplicación "usuarios", que es una subaplicación de nuestro proyecto Django. En el método ready() importamos el módulo signals para asegurarnos de que las señales se registren correctamente cuando la aplicación esté lista. Esto es importante para que las señales se ejecuten en el momento adecuado, como después de migrar la base de datos, para crear los grupos y permisos necesarios.
class UsuariosConfig(AppConfig):
    name = "usuarios"

    def ready(self):
        from . import signals  # noqa: F401
