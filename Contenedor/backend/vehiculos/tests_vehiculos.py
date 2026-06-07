from django.test import TestCase, RequestFactory
from vehiculos.models import Vehiculo, Modelo, Marca
from vehiculos.views import buscar_vehiculo, agregar_vehiculo, modificar_datos, mostrar_detalle_view
from django.core.files.uploadedfile import SimpleUploadedFile
from vehiculos.forms import VehiculoForm
from vehiculos.models import Vehiculo, Modelo, Marca, TipoVehiculo, EstadoVehiculo
import io
from PIL import Image
from django.contrib.auth import get_user_model
from django.http import Http404
from django.urls import reverse
from django.db import IntegrityError, connection, transaction

# =====================================================================
# PRUEBA 1: METODO BUSCAR VEHICULO
# =====================================================================
class BuscarVehiculoTestCase(TestCase):
    
    def setUp(self):
        """
        Contexto (Arrange): Preparamos la base de datos de prueba.
        Creamos las dependencias de claves foráneas y dos vehículos de prueba:
        uno que cumple todas las condiciones y otro que está inactivo.
        """
        self.duenio = Usuario.objects.create_user(
            username='duenio_busqueda',
            email='duenio_busqueda@test.com',
            password='123',
            dni='11111111'
        )

        # 1. Creamos las entidades relacionadas necesarias
        self.marca = Marca.objects.create(nombre="Toyota")
        self.modelo = Modelo.objects.create(nombre="Corolla", marca=self.marca)

        # 2. Vehículo de prueba 1 (Activo y disponible)
        self.vehiculo_activo = Vehiculo.objects.create(
            matricula="AF 123 XZ",  
            precio_x_dia=15000.00,
            modelo=self.modelo,
            duenio=self.duenio,
            activo=True,
            esta_aprobado=True
        )
        
        # 3. Vehículo de prueba 2 (Inactivo / Dado de baja)
        self.vehiculo_inactivo = Vehiculo.objects.create(
            matricula="AB 987 YZ",
            precio_x_dia=10000.00,
            modelo=self.modelo,
            duenio=self.duenio,
            activo=False,
            esta_aprobado=True
        )

    def test_buscar_vehiculo_camino_feliz(self):
        """
        Prueba 1: Búsqueda exacta de un vehículo activo.
        Verifica que el método retorne un QuerySet con 1 elemento y sea el correcto.
        """
        # Ejecución (Act)
        resultado = buscar_vehiculo("AF 123 XZ") 
        
        # Comprobación (Assert)
        self.assertEqual(resultado.count(), 1)
        self.assertEqual(resultado.first().matricula, "AF 123 XZ")

    def test_buscar_vehiculo_insensible_a_mayusculas(self):
        """
        Prueba 2: Búsqueda en minúsculas (Validación del __iexact).
        Verifica que el ORM lo encuentre a pesar de que en la BD está en mayúsculas.
        """
        # El usuario escribe todo en minúsculas en el buscador
        resultado = buscar_vehiculo("af 123 xz") 
        
        self.assertEqual(resultado.count(), 1)
        self.assertEqual(resultado.first().matricula, "AF 123 XZ")

    def test_buscar_vehiculo_inactivo_no_retorna_resultados(self):
        """
        Prueba 3: Validación de regla de negocio (activo=True).
        Verifica que si se busca una matrícula real, pero el auto está de baja, no se muestre.
        """
        # Buscamos la matrícula del vehículo inactivo
        resultado = buscar_vehiculo("AB 987 YZ") 
        
        # El QuerySet debe estar vacío (count = 0) porque el método filtra por activo=True
        self.assertEqual(resultado.count(), 0) 

    def test_buscar_vehiculo_inexistente(self):
        """
        Prueba 4: Búsqueda de un dato que no existe en el sistema.
        Verifica que el sistema no lance una excepción (crashee) y simplemente retorne vacío.
        """
        resultado = buscar_vehiculo("ZZ 000 ZZ")
        
        self.assertEqual(resultado.count(), 0)



# =====================================================================
# PRUEBA 2: METODO VALIDAR DATOS
# =====================================================================
class ValidarDatosTestCase(TestCase):
    
    def setUp(self):
        """
        Contexto (Arrange): Preparamos las dependencias (Claves Foráneas) que 
        el formulario necesita para poder renderizarse y validarse correctamente.
        """
        self.duenio = Usuario.objects.create_user(
            username='duenio_form',
            email='duenio_form@test.com',
            password='123',
            dni='11112222'
        )

        self.marca = Marca.objects.create(nombre="Ford")
        self.modelo = Modelo.objects.create(nombre="Fiesta", marca=self.marca)
        self.tipo = TipoVehiculo.objects.create(nombre="Auto")
        self.estado = EstadoVehiculo.objects.create(nombre="Excelente")
        
        # Creamos una imagen REAL de 1x1 píxel en memoria usando Pillow
        archivo_imagen = io.BytesIO()
        imagen_falsa = Image.new('RGB', (1, 1), color='red')
        imagen_falsa.save(archivo_imagen, format='JPEG')
        
        self.imagen_mock = SimpleUploadedFile(
            name='test_image.jpg', 
            content=archivo_imagen.getvalue(), 
            content_type='image/jpeg'
        )
        
        # Creamos un vehículo para poder probar la regla de "Matrícula Única"
        self.vehiculo_existente = Vehiculo.objects.create(
            matricula="AF 123 XZ",
            precio_x_dia=10000.00,
            modelo=self.modelo,
            duenio=self.duenio,
            tipo_vehiculo=self.tipo,
            estado_vehiculo=self.estado,
            activo=True,
            esta_aprobado=True
        )

    def test_validar_datos_camino_feliz(self):
        """
        Prueba 1: Datos perfectos.
        El método is_valid() debe devolver True y validar_datos() debe pasar sin errores.
        """
        datos = {
            'matricula': 'AB 123 CD', 
            'precio_x_dia': 15000.00,
            'modelo': self.modelo.id,
            'tipo_vehiculo': self.tipo.id,
            'estado_vehiculo': self.estado.id,
        }
        form = VehiculoForm(data=datos, files={'imagen': self.imagen_mock})
        
        self.assertTrue(form.is_valid())

    def test_validar_datos_matricula_formato_invalido(self):
        """
        Prueba 2: Violación del Regex.
        Simula un usuario ingresando mal la matrícula (ej. sin espacios o letras de más).
        """
        datos = {
            'matricula': 'ABC1234X', # Formato incorrecto, falla el regex
            'precio_x_dia': 15000.00,
            'modelo': self.modelo.id,
            'tipo_vehiculo': self.tipo.id,
            'estado_vehiculo': self.estado.id,
        }
        form = VehiculoForm(data=datos, files={'imagen': self.imagen_mock})
        
        self.assertFalse(form.is_valid())
        self.assertIn('matricula', form.errors) # Verifica que el error esté específicamente en ese campo

    def test_validar_datos_matricula_duplicada(self):
        """
        Prueba 3: Violación de Unicidad.
        Simula ingresar la patente de un auto que ya instanciamos en el setUp.
        """
        datos = {
            'matricula': 'AF 123 XZ', # Ya existe en la base de datos
            'precio_x_dia': 15000.00,
            'modelo': self.modelo.id,
            'tipo_vehiculo': self.tipo.id,
            'estado_vehiculo': self.estado.id,
        }
        form = VehiculoForm(data=datos, files={'imagen': self.imagen_mock})
        
        self.assertFalse(form.is_valid())
        self.assertIn('matricula', form.errors)

    def test_validar_datos_precio_negativo(self):
        """
        Prueba 4: Lógica de negocio.
        Verifica que la regla de _validar_precio bloquee números negativos.
        """
        datos = {
            'matricula': 'ZZ 999 YY',
            'precio_x_dia': -500.00, # Precio ilógico
            'modelo': self.modelo.id,
            'tipo_vehiculo': self.tipo.id,
            'estado_vehiculo': self.estado.id,
        }
        form = VehiculoForm(data=datos, files={'imagen': self.imagen_mock})
        
        self.assertFalse(form.is_valid())
        self.assertIn('precio_x_dia', form.errors)



# =====================================================================
# PRUEBA 3: METODO AGREGAR VEHICULO
# =====================================================================
Usuario = get_user_model()
class AgregarVehiculoTestCase(TestCase):
    
    def setUp(self):
        """
        Contexto (Arrange): Preparamos las dependencias obligatorias.
        """
        self.usuario = Usuario.objects.create_user(username='socio_add', email='add@test.com', password='123', dni='12345678')
        self.marca = Marca.objects.create(nombre="Renault")
        self.modelo = Modelo.objects.create(nombre="Sandero", marca=self.marca)
        self.tipo = TipoVehiculo.objects.create(nombre="Auto")
        self.estado = EstadoVehiculo.objects.create(nombre="Disponible")
        
        # Guardamos un vehículo inicial para probar el caso de la patente duplicada
        self.vehiculo_existente = Vehiculo.objects.create(
            matricula="AG 123 CD", precio_x_dia=15000.0, modelo=self.modelo,
            tipo_vehiculo=self.tipo, estado_vehiculo=self.estado, duenio=self.usuario, activo=True
        )

    # CASO 1: Camino Feliz
    def test_agregar_vehiculo_camino_feliz(self):
        """Verifica que un vehículo válido se guarde físicamente en la BD."""
        nuevo_vehiculo = Vehiculo(
            matricula="AA 111 AA", precio_x_dia=15000.0, modelo=self.modelo,
            tipo_vehiculo=self.tipo, estado_vehiculo=self.estado, duenio=self.usuario, activo=True
        )
        
        vehiculo_retornado = agregar_vehiculo(nuevo_vehiculo)
        
        self.assertIsNotNone(vehiculo_retornado.id)
        # El conteo debe ser 2 (el del setUp + este nuevo)
        self.assertEqual(Vehiculo.objects.count(), 2) 

    # CASO 2: Falla de Unicidad (Matrícula Duplicada)
    def test_agregar_vehiculo_matricula_duplicada_lanza_error(self):
        """Verifica que la restricción UNIQUE de la BD bloquee patentes repetidas."""
        vehiculo_duplicado = Vehiculo(
            matricula="AG 123 CD", 
            precio_x_dia=15000.0, modelo=self.modelo,
            tipo_vehiculo=self.tipo, estado_vehiculo=self.estado, duenio=self.usuario, activo=True
        )
        
        # assertRaises verifica que la base de datos lance la excepción IntegrityError
        with self.assertRaises(IntegrityError):
            agregar_vehiculo(vehiculo_duplicado)

    # CASO 3: Dato Faltante / Integridad (Dueño Nulo)
    def test_agregar_vehiculo_duenio_none_lanza_error(self):
        """Verifica que la restricción NOT NULL/Foreign Key bloquee el guardado si no hay dueño."""
        vehiculo_sin_duenio = Vehiculo(
            matricula="BB 222 BB", precio_x_dia=15000.0, modelo=self.modelo,
            tipo_vehiculo=self.tipo, estado_vehiculo=self.estado, 
            duenio=None, 
            activo=True
        )
        
        with self.assertRaises(IntegrityError):
            agregar_vehiculo(vehiculo_sin_duenio)

    # CASO 4: Dato Faltante (NOT NULL)
    def test_agregar_vehiculo_dato_faltante_lanza_error(self):
        """Verifica que la restricción NOT NULL de la BD bloquee el guardado si falta un dato obligatorio."""
        vehiculo_incompleto = Vehiculo(
            matricula=None, # <-- Usamos None en la patente porque es estrictamente obligatorio en BD
            precio_x_dia=15000.0, modelo=self.modelo,
            tipo_vehiculo=self.tipo, estado_vehiculo=self.estado, duenio=self.usuario, activo=True
        )
        
        with self.assertRaises(IntegrityError):
            agregar_vehiculo(vehiculo_incompleto)

    # CASO 5: Integridad Referencial (Modelo Inexistente)
    def test_agregar_vehiculo_modelo_inexistente_lanza_error(self):
        """Verifica que no se pueda asociar el auto a un ID de modelo que no existe."""
        vehiculo_modelo_roto = Vehiculo(
            matricula="CC 333 CC", precio_x_dia=15000.0, 
            modelo_id=9999, # <-- Ponemos un ID de modelo que jamás creamos
            tipo_vehiculo=self.tipo, estado_vehiculo=self.estado, duenio=self.usuario, activo=True
        )
        
        # Esperamos que salte el IntegrityError
        with self.assertRaises(IntegrityError):
            
            # Envolvemos la prueba en una transacción atómica
            with transaction.atomic():
                agregar_vehiculo(vehiculo_modelo_roto)
                
                # Forzamos la validación en SQLite. Al saltar el error acá,
                # la transacción atómica hace un ROLLBACK automático y borra la basura.
                if connection.vendor == 'sqlite':
                    connection.check_constraints()



# =====================================================================
# PRUEBA 4: METODO MODIFICAR DATOS
# =====================================================================
class ModificarDatosTestCase(TestCase):
    
    def setUp(self):
        """Contexto: Preparamos un vehículo que ya existe en la base de datos."""
        self.usuario = Usuario.objects.create_user(username='socio2', email='socio2@test.com', password='123', dni='22222222')
        self.marca = Marca.objects.create(nombre="Chevrolet")
        self.modelo = Modelo.objects.create(nombre="Cruze", marca=self.marca)
        self.tipo = TipoVehiculo.objects.create(nombre="Auto")
        self.estado = EstadoVehiculo.objects.create(nombre="Excelente")

        self.vehiculo = Vehiculo.objects.create(
            matricula="AD 456 WW",
            precio_x_dia=20000.00,
            modelo=self.modelo,
            tipo_vehiculo=self.tipo,
            estado_vehiculo=self.estado,
            duenio=self.usuario,
            activo=True,
            esta_aprobado=True
        )

    def test_modificar_datos_postcondicion(self):
        """
        Verifica que al alterar una instancia en memoria e invocar la operación,
        los cambios se reflejen físicamente en la base de datos (UPDATE).
        """
        #Traemos el vehículo y le cambiamos un dato en memoria
        vehiculo_a_editar = Vehiculo.objects.get(id=self.vehiculo.id)
        vehiculo_a_editar.precio_x_dia = 25000.00 

        #Invocamos la operación
        vehiculo_retornado = modificar_datos(vehiculo_a_editar)

        #Comprobamos que la base de datos se haya actualizado
        vehiculo_en_bd = Vehiculo.objects.get(id=self.vehiculo.id)
        self.assertEqual(vehiculo_en_bd.precio_x_dia, 25000.00)
        self.assertEqual(vehiculo_retornado.precio_x_dia, 25000.00)


# =====================================================================
# PRUEBA 5: METODO MOSTRAR DETALLE VIEW
# =====================================================================
class MostrarDetalleViewTestCase(TestCase):
    
    def setUp(self):
        """Contexto: Preparamos el entorno para simular peticiones web."""
        # Creamos dos usuarios: el dueño del auto y un visitante cualquiera
        self.duenio = Usuario.objects.create_user(username='duenio', email='duenio@test.com', password='123', dni='33333333')
        self.visitante = Usuario.objects.create_user(username='visitante', email='visitante@test.com', password='123', dni='44444444')
        
        self.marca = Marca.objects.create(nombre="Fiat")
        self.modelo = Modelo.objects.create(nombre="Cronos", marca=self.marca)
        self.tipo = TipoVehiculo.objects.create(nombre="Auto")
        self.estado = EstadoVehiculo.objects.create(nombre="Bueno")

        # Vehículo activo disponible para ver
        self.vehiculo_activo = Vehiculo.objects.create(
            matricula="AG 111 GG", precio_x_dia=18000.00, modelo=self.modelo,
            tipo_vehiculo=self.tipo, estado_vehiculo=self.estado,
            duenio=self.duenio, activo=True, esta_aprobado=True
        )
        
        # Vehículo inactivo (dado de baja lógica)
        self.vehiculo_inactivo = Vehiculo.objects.create(
            matricula="ZZ 000 ZZ", precio_x_dia=15000.00, modelo=self.modelo,
            tipo_vehiculo=self.tipo, estado_vehiculo=self.estado,
            duenio=self.duenio, activo=False, esta_aprobado=True
        )

    def test_detalle_vehiculo_activo_devuelve_200(self):
        """Verifica que un vehículo activo se pueda visualizar correctamente."""
        self.client.force_login(self.visitante)
        
        #Usamos reverse con el 'name' de urls.py y le pasamos el ID
        url = reverse('detalle_vehiculo', args=[self.vehiculo_activo.id])
        respuesta = self.client.get(url)
        
        # Código 200 significa "OK - Página encontrada"
        self.assertEqual(respuesta.status_code, 200)

    def test_detalle_identifica_al_duenio(self):
        """Verifica la lógica de negocio: 'puede_editar' debe ser True solo si es el dueño."""
        self.client.force_login(self.duenio)
        url = reverse('detalle_vehiculo', args=[self.vehiculo_activo.id])
        respuesta = self.client.get(url)
        
        self.assertTrue(respuesta.context['puede_editar'])

    def test_detalle_vehiculo_inactivo_devuelve_404(self):
        """Verifica que el sistema impida visualizar vehículos dados de baja."""
        self.client.force_login(self.visitante)
        url = reverse('detalle_vehiculo', args=[self.vehiculo_inactivo.id])
        respuesta = self.client.get(url)
        
        self.assertEqual(respuesta.status_code, 404)


# =====================================================================
# PRUEBA 6: METODO LISTAR VEHICULOS VIEW
# =====================================================================
class ListarVehiculosViewTestCase(TestCase):
    
    def setUp(self):
        """Contexto: Creamos usuarios y vehículos en diferentes estados lógicos."""
        self.socio = Usuario.objects.create_user(username='socio_lista', email='socio@test.com', password='123', dni='55555555')
        
        self.marca = Marca.objects.create(nombre="Renault")
        self.modelo = Modelo.objects.create(nombre="Sandero", marca=self.marca)
        self.tipo = TipoVehiculo.objects.create(nombre="Auto")
        self.estado = EstadoVehiculo.objects.create(nombre="Bueno")

        # 1. Vehículo Activo (Debe aparecer en la lista)
        self.vehiculo_valido = Vehiculo.objects.create(
            matricula="AA 111 AA", precio_x_dia=10000.00, modelo=self.modelo,
            tipo_vehiculo=self.tipo, estado_vehiculo=self.estado,
            duenio=self.socio, activo=True, esta_aprobado=True
        )

        # 2. Vehículo Inactivo (No debe aparecer)
        self.vehiculo_inactivo = Vehiculo.objects.create(
            matricula="BB 222 BB", precio_x_dia=12000.00, modelo=self.modelo,
            tipo_vehiculo=self.tipo, estado_vehiculo=self.estado,
            duenio=self.socio, activo=False, esta_aprobado=True
        )

    def test_listar_vehiculos_filtra_correctamente(self):
        """Verifica que la vista solo exponga vehículos activos."""
        self.client.force_login(self.socio)
        
        url = reverse('lista_vehiculos') 
        respuesta = self.client.get(url)
        
        self.assertEqual(respuesta.status_code, 200)
        
        # Evaluamos el QuerySet que la vista le envía al Template
        vehiculos_en_lista = respuesta.context['vehiculos']
        
        # Comprobaciones de las Reglas de Negocio
        self.assertIn(self.vehiculo_valido, vehiculos_en_lista)
        self.assertNotIn(self.vehiculo_inactivo, vehiculos_en_lista)


# =====================================================================
# PRUEBA 7: METODO PROCESAR BAJA VEHICULO
# =====================================================================
class ProcesarBajaVehiculoTestCase(TestCase):
    
    def setUp(self):
        """Contexto: Creamos un vehículo inicialmente activo en el sistema."""
        self.socio = Usuario.objects.create_user(username='socio_baja', email='baja@test.com', password='123', dni='66666666')
        self.marca = Marca.objects.create(nombre="Nissan")
        self.modelo = Modelo.objects.create(nombre="Frontier", marca=self.marca)
        self.tipo = TipoVehiculo.objects.create(nombre="Camioneta")
        self.estado = EstadoVehiculo.objects.create(nombre="Excelente")

        self.vehiculo = Vehiculo.objects.create(
            matricula="AA 999 ZZ", precio_x_dia=30000.00, modelo=self.modelo,
            tipo_vehiculo=self.tipo, estado_vehiculo=self.estado,
            duenio=self.socio, activo=True, esta_aprobado=True
        )

    def test_procesar_baja_modifica_estado_logico(self):
        """Verifica que la petición POST apague el flag 'activo' sin borrar el registro."""
        #Iniciamos sesión y verificamos precondiciones
        self.client.force_login(self.socio)
        self.assertEqual(Vehiculo.objects.count(), 1)
        self.assertTrue(self.vehiculo.activo)

        #Simulamos la petición HTTP POST enviando el formulario de eliminación
        url = reverse('mis_vehiculos')
        respuesta = self.client.post(url, {
            'accion': 'eliminar',
            'vehiculo_id': self.vehiculo.id
        })

        #Recargamos el vehículo desde la BD para ver si mutó
        vehiculo_bd = Vehiculo.objects.get(id=self.vehiculo.id)
        
        self.assertFalse(vehiculo_bd.activo) # La baja lógica funcionó
        self.assertEqual(Vehiculo.objects.count(), 1) # No se borró físicamente
        self.assertEqual(respuesta.status_code, 302) # Validamos que el servidor haya respondido con una redirección de éxito