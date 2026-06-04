from django.apps import AppConfig

# Definimos la configuración de la aplicación "usuarios", que es una subaplicación de nuestro proyecto Django. En el método ready() importamos el módulo signals para asegurarnos de que las señales se registren correctamente cuando la aplicación esté lista. Esto es importante para que las señales se ejecuten en el momento adecuado, como después de migrar la base de datos, para crear los grupos y permisos necesarios.
class UsuariosConfig(AppConfig):
    name = "usuarios"
    # El método ready() se ejecuta cuando la aplicación está lista, y es el lugar adecuado para importar el módulo de señales para asegurarnos de que se registren correctamente. Esto es crucial para que las señales se ejecuten en el momento adecuado, como después de migrar la base de datos, para crear los grupos y permisos necesarios.
    def ready(self):
        from . import signals  # Importamos el módulo de señales para que se registren correctamente y se ejecuten en el momento adecuado, como después de migrar la base de datos, para crear los grupos y permisos necesarios.
