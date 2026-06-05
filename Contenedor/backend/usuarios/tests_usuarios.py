from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


Usuario = get_user_model()


def _asegurar_grupos(*nombres):
	for nombre in nombres:
		Group.objects.get_or_create(name=nombre)


# =====================================================================
# PRUEBA 1: METODO REGISTRO
# =====================================================================
class RegistroUsuarioViewTestCase(TestCase):
	def setUp(self):
		_asegurar_grupos('Clientes', 'Socios', 'Administradores')

	def test_registro_crea_usuario_y_asigna_grupo_cliente(self):
		respuesta = self.client.post(reverse('registro'), {
			'email': 'nuevo_cliente@example.com',
			'dni': '12345678',
			'first_name': 'Nuevo',
			'last_name': 'Cliente',
			'username': 'nuevo_cliente',
			'rol': 'Clientes',
			'password1': 'Testpass123',
			'password2': 'Testpass123',
		})

		self.assertEqual(respuesta.status_code, 302)
		self.assertEqual(respuesta.url, reverse('login'))

		usuario = Usuario.objects.get(email='nuevo_cliente@example.com')
		self.assertTrue(usuario.groups.filter(name='Clientes').exists())
		self.assertFalse(usuario.groups.filter(name='Socios').exists())


# =====================================================================
# PRUEBA 2: METODO LOGIN
# =====================================================================
class LoginViewTestCase(TestCase):
	def setUp(self):
		self.usuario = Usuario.objects.create_user(
			username='usuario_login',
			email='login@example.com',
			dni='23456789',
			password='Testpass123',
		)

	def test_login_camino_feliz(self):
		respuesta = self.client.post(reverse('login'), {
			'email': 'login@example.com',
			'password': 'Testpass123',
		})

		self.assertEqual(respuesta.status_code, 302)
		self.assertEqual(respuesta.url, reverse('inicio'))
		self.assertEqual(self.client.session.get('_auth_user_id'), str(self.usuario.id))

	def test_login_credenciales_invalidas_muestra_error(self):
		respuesta = self.client.post(reverse('login'), {
			'email': 'login@example.com',
			'password': 'incorrecta',
		})

		self.assertEqual(respuesta.status_code, 200)
		self.assertIn('error', respuesta.context)
		self.assertIn('incorrectos', respuesta.context['error'])


# =====================================================================
# PRUEBA 3: METODO LOGOUT
# =====================================================================
class LogoutViewTestCase(TestCase):
	def setUp(self):
		self.usuario = Usuario.objects.create_user(
			username='usuario_logout',
			email='logout@example.com',
			dni='34567890',
			password='Testpass123',
		)

	def test_logout_cierra_sesion_y_redirige(self):
		self.client.force_login(self.usuario)

		respuesta = self.client.get(reverse('logout'))

		self.assertEqual(respuesta.status_code, 302)
		self.assertEqual(respuesta.url, reverse('inicio'))
		self.assertIsNone(self.client.session.get('_auth_user_id'))


# =====================================================================
# PRUEBA 4: METODO ABM USUARIOS
# =====================================================================
class AbmUsuariosViewTestCase(TestCase):
	def setUp(self):
		_asegurar_grupos('Clientes', 'Socios', 'Administradores')
		self.admin = Usuario.objects.create_user(
			username='admin_abm',
			email='admin_abm@example.com',
			dni='45678901',
			password='Testpass123',
		)
		self.admin.groups.add(Group.objects.get(name='Administradores'))

		self.cliente_objetivo = Usuario.objects.create_user(
			username='cliente_objetivo',
			email='cliente_objetivo@example.com',
			dni='56789012',
			password='Testpass123',
		)
		self.cliente_objetivo.groups.add(Group.objects.get(name='Clientes'))

		self.socio_objetivo = Usuario.objects.create_user(
			username='socio_objetivo',
			email='socio_objetivo@example.com',
			dni='67890123',
			password='Testpass123',
		)
		self.socio_objetivo.groups.add(Group.objects.get(name='Socios'))

		for indice in range(10):
			usuario = Usuario.objects.create_user(
				username=f'cliente_{indice}',
				email=f'cliente_{indice}@example.com',
				dni=f'700000{indice:02d}',
				password='Testpass123',
			)
			usuario.groups.add(Group.objects.get(name='Clientes'))

	def test_abm_filtra_por_busqueda_y_grupo(self):
		self.client.force_login(self.admin)

		respuesta = self.client.get(reverse('abm_usuarios'), {'q': 'socio_objetivo', 'grupo': 'Socios'})

		self.assertEqual(respuesta.status_code, 200)
		usuarios = list(respuesta.context['usuarios'])
		self.assertIn(self.socio_objetivo, usuarios)
		self.assertNotIn(self.cliente_objetivo, usuarios)
		self.assertEqual(respuesta.context['grupo_seleccionado'], 'Socios')
		self.assertEqual(respuesta.context['busqueda'], 'socio_objetivo')

	def test_abm_pagina_resultados(self):
		self.client.force_login(self.admin)

		respuesta = self.client.get(reverse('abm_usuarios'), {'page': 2})

		self.assertEqual(respuesta.status_code, 200)
		self.assertEqual(len(respuesta.context['usuarios']), 3)
		self.assertEqual(respuesta.context['page_obj'].number, 2)


# =====================================================================
# PRUEBA 5: METODO EDITAR USUARIO
# =====================================================================
class EditarUsuarioViewTestCase(TestCase):
	def setUp(self):
		_asegurar_grupos('Clientes', 'Socios', 'Administradores')
		self.admin = Usuario.objects.create_user(
			username='admin_edicion',
			email='admin_edicion@example.com',
			dni='78901234',
			password='Testpass123',
		)
		self.admin.groups.add(Group.objects.get(name='Administradores'))

		self.usuario = Usuario.objects.create_user(
			username='usuario_editable',
			email='editable@example.com',
			dni='89012345',
			password='Testpass123',
		)
		self.usuario.groups.add(Group.objects.get(name='Clientes'))

	def test_editar_usuario_actualiza_datos_y_rol(self):
		self.client.force_login(self.admin)

		respuesta = self.client.post(reverse('editar_usuario', args=[self.usuario.id]), {
			'email': 'editado@example.com',
			'dni': '90123456',
			'first_name': 'Nombre',
			'last_name': 'Nuevo',
			'username': 'usuario_editado',
			'rol': 'Administradores',
		})

		self.assertEqual(respuesta.status_code, 302)
		self.assertEqual(respuesta.url, reverse('abm_usuarios'))

		self.usuario.refresh_from_db()
		self.assertEqual(self.usuario.email, 'editado@example.com')
		self.assertEqual(self.usuario.dni, '90123456')
		self.assertEqual(self.usuario.username, 'usuario_editado')
		self.assertTrue(self.usuario.groups.filter(name='Administradores').exists())
		self.assertFalse(self.usuario.groups.filter(name='Clientes').exists())


# =====================================================================
# PRUEBA 6: METODO SUSPENDER Y REACTIVAR USUARIO
# =====================================================================
class SuspenderReactivarUsuarioViewTestCase(TestCase):
	def setUp(self):
		_asegurar_grupos('Clientes', 'Socios', 'Administradores')
		self.admin = Usuario.objects.create_user(
			username='admin_estado',
			email='admin_estado@example.com',
			dni='01234567',
			password='Testpass123',
		)
		self.admin.groups.add(Group.objects.get(name='Administradores'))

		self.usuario = Usuario.objects.create_user(
			username='usuario_estado',
			email='estado@example.com',
			dni='11223344',
			password='Testpass123',
		)

	def test_suspender_usuario_desactiva(self):
		self.client.force_login(self.admin)

		respuesta = self.client.post(reverse('suspender_usuario', args=[self.usuario.id]))

		self.assertEqual(respuesta.status_code, 302)
		self.usuario.refresh_from_db()
		self.assertFalse(self.usuario.is_active)

	def test_reactivar_usuario_activa(self):
		self.usuario.is_active = False
		self.usuario.save(update_fields=['is_active'])
		self.client.force_login(self.admin)

		respuesta = self.client.post(reverse('reactivar_usuario', args=[self.usuario.id]))

		self.assertEqual(respuesta.status_code, 302)
		self.usuario.refresh_from_db()
		self.assertTrue(self.usuario.is_active)
