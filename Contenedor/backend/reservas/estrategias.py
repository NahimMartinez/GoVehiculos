from abc import ABC, abstractmethod
from decimal import Decimal
import hashlib
import random
import time
import unicodedata


# 1. La Interfaz de la Estrategia
class EstrategiaPago(ABC):
    @abstractmethod
    def calcular_total(self, monto_base: Decimal) -> Decimal:
        """Calcula el monto final aplicando reglas específicas del método de pago."""
        pass

    @abstractmethod
    def obtener_campos_requeridos(self) -> list:
        """Retorna la lista de campos requeridos para el formulario de pago dinámico."""
        pass

    @abstractmethod
    def validar_datos(self, datos_pago: dict) -> dict:
        """Valida los datos de pago según la estrategia. Retorna {'valido': bool, 'errores': []}."""
        pass

    @abstractmethod
    def procesar_pago(self, datos_pago: dict) -> dict:
        """Simula el procesamiento del pago. Retorna {'exito': bool, 'mensaje': str, 'comprobante': str, 'detalle': dict}."""
        pass

    def _generar_comprobante(self, prefijo: str) -> str:
        """Genera un comprobante de transacción con formato realista."""
        timestamp = int(time.time())
        aleatorio = random.randint(100000, 999999)
        # Simula un hash parcial como haría un procesador real
        seed = f'{prefijo}-{timestamp}-{aleatorio}'
        hash_parcial = hashlib.sha256(seed.encode()).hexdigest()[:8].upper()
        return f'{prefijo}-{timestamp}-{hash_parcial}'


# 2. Estrategias Concretas

class EstrategiaTarjetaCredito(EstrategiaPago):
    RECARGO = Decimal('0.10')  # 10% de recargo

    def calcular_total(self, monto_base: Decimal) -> Decimal:
        recargo = monto_base * self.RECARGO
        return monto_base + recargo

    def obtener_campos_requeridos(self) -> list:
        return [
            {'nombre': 'numero_tarjeta', 'label': 'Número de tarjeta', 'tipo': 'text', 'maxlength': 16, 'placeholder': '0000 0000 0000 0000', 'patron': r'^\d{16}$'},
            {'nombre': 'nombre_titular', 'label': 'Nombre del titular', 'tipo': 'text', 'maxlength': 100, 'placeholder': 'Como figura en la tarjeta'},
            {'nombre': 'vencimiento_mes', 'label': 'Mes de vencimiento', 'tipo': 'select', 'opciones': [f'{i:02d}' for i in range(1, 13)]},
            {'nombre': 'vencimiento_anio', 'label': 'Año de vencimiento', 'tipo': 'select', 'opciones': [str(2026 + i) for i in range(10)]},
            {'nombre': 'codigo_seguridad', 'label': 'Código de seguridad (CVV)', 'tipo': 'text', 'maxlength': 3, 'placeholder': '***', 'patron': r'^\d{3}$'},
            {'nombre': 'franquicia_id', 'label': 'Franquicia', 'tipo': 'franquicia', 'tipo_tarjeta': 'credito'},
        ]

    def validar_datos(self, datos_pago: dict) -> dict:
        errores = []

        numero_tarjeta = datos_pago.get('numero_tarjeta', '').replace(' ', '')
        if not numero_tarjeta or len(numero_tarjeta) != 16 or not numero_tarjeta.isdigit():
            errores.append('El número de tarjeta debe tener 16 dígitos.')
        elif not self._validar_luhn(numero_tarjeta):
            errores.append('El número de tarjeta no es válido.')

        nombre_titular = datos_pago.get('nombre_titular', '').strip()
        if not nombre_titular:
            errores.append('El nombre del titular es obligatorio.')

        vencimiento_mes = datos_pago.get('vencimiento_mes', '')
        vencimiento_anio = datos_pago.get('vencimiento_anio', '')
        if not vencimiento_mes or not vencimiento_anio:
            errores.append('La fecha de vencimiento es obligatoria.')

        codigo_seguridad = datos_pago.get('codigo_seguridad', '').strip()
        if not codigo_seguridad or len(codigo_seguridad) != 3 or not codigo_seguridad.isdigit():
            errores.append('El código de seguridad debe tener 3 dígitos.')

        if not datos_pago.get('franquicia_id'):
            errores.append('Debe seleccionar una franquicia de tarjeta.')

        return {'valido': len(errores) == 0, 'errores': errores}

    def procesar_pago(self, datos_pago: dict) -> dict:
        time.sleep(2)  # Simula latencia de procesador de pagos

        # Simulamos un rechazo aleatorio del 5% para mayor realismo
        if random.random() < 0.05:
            return {
                'exito': False,
                'mensaje': 'La entidad emisora rechazó la transacción. Intente nuevamente o use otra tarjeta.',
                'comprobante': None,
                'detalle': {},
            }

        numero_tarjeta = datos_pago.get('numero_tarjeta', '').replace(' ', '')
        comprobante = self._generar_comprobante('TRX-CC')

        return {
            'exito': True,
            'mensaje': 'Pago con tarjeta de crédito procesado exitosamente.',
            'comprobante': comprobante,
            'detalle': {
                'ultimos_4_digitos': numero_tarjeta[-4:] if len(numero_tarjeta) >= 4 else '',
                'nombre_titular': datos_pago.get('nombre_titular', ''),
                'franquicia_id': datos_pago.get('franquicia_id'),
            },
        }

    @staticmethod
    def _validar_luhn(numero: str) -> bool:
        """Implementación del algoritmo de Luhn para validación de números de tarjeta."""
        digitos = [int(d) for d in numero]
        digitos.reverse()
        total = 0
        for i, digito in enumerate(digitos):
            if i % 2 == 1:
                digito *= 2
                if digito > 9:
                    digito -= 9
            total += digito
        return total % 10 == 0


class EstrategiaTarjetaDebito(EstrategiaPago):
    def calcular_total(self, monto_base: Decimal) -> Decimal:
        # La tarjeta de débito cobra el precio de lista (sin alteraciones)
        return monto_base

    def obtener_campos_requeridos(self) -> list:
        return [
            {'nombre': 'numero_tarjeta', 'label': 'Número de tarjeta', 'tipo': 'text', 'maxlength': 16, 'placeholder': '0000 0000 0000 0000', 'patron': r'^\d{16}$'},
            {'nombre': 'nombre_titular', 'label': 'Nombre del titular', 'tipo': 'text', 'maxlength': 100, 'placeholder': 'Como figura en la tarjeta'},
            {'nombre': 'codigo_seguridad', 'label': 'Código de seguridad', 'tipo': 'text', 'maxlength': 4, 'placeholder': '****', 'patron': r'^\d{4}$'},
            {'nombre': 'franquicia_id', 'label': 'Franquicia', 'tipo': 'franquicia', 'tipo_tarjeta': 'debito'},
        ]

    def validar_datos(self, datos_pago: dict) -> dict:
        errores = []

        numero_tarjeta = datos_pago.get('numero_tarjeta', '').replace(' ', '')
        if not numero_tarjeta or len(numero_tarjeta) != 16 or not numero_tarjeta.isdigit():
            errores.append('El número de tarjeta debe tener 16 dígitos.')

        nombre_titular = datos_pago.get('nombre_titular', '').strip()
        if not nombre_titular:
            errores.append('El nombre del titular es obligatorio.')

        codigo_seguridad = datos_pago.get('codigo_seguridad', '').strip()
        if not codigo_seguridad or len(codigo_seguridad) != 4 or not codigo_seguridad.isdigit():
            errores.append('El código de seguridad debe tener 4 dígitos.')

        if not datos_pago.get('franquicia_id'):
            errores.append('Debe seleccionar una franquicia de tarjeta.')

        return {'valido': len(errores) == 0, 'errores': errores}

    def procesar_pago(self, datos_pago: dict) -> dict:
        time.sleep(2)  # Simula latencia de API

        if random.random() < 0.05:
            return {
                'exito': False,
                'mensaje': 'Fondos insuficientes. Verifique el saldo de su cuenta.',
                'comprobante': None,
                'detalle': {},
            }

        numero_tarjeta = datos_pago.get('numero_tarjeta', '').replace(' ', '')
        comprobante = self._generar_comprobante('TRX-DB')

        return {
            'exito': True,
            'mensaje': 'Pago con tarjeta de débito procesado exitosamente.',
            'comprobante': comprobante,
            'detalle': {
                'ultimos_4_digitos': numero_tarjeta[-4:] if len(numero_tarjeta) >= 4 else '',
                'nombre_titular': datos_pago.get('nombre_titular', ''),
                'franquicia_id': datos_pago.get('franquicia_id'),
            },
        }


class EstrategiaTransferencia(EstrategiaPago):
    DESCUENTO = Decimal('0.05')  # 5% de descuento

    def calcular_total(self, monto_base: Decimal) -> Decimal:
        descuento = monto_base * self.DESCUENTO
        return monto_base - descuento

    def obtener_campos_requeridos(self) -> list:
        return [
            {'nombre': 'cbu_cvu', 'label': 'CBU / CVU', 'tipo': 'text', 'maxlength': 22, 'placeholder': '0000000000000000000000', 'patron': r'^\d{22}$'},
            {'nombre': 'titular_cuenta', 'label': 'Titular de la cuenta', 'tipo': 'text', 'maxlength': 100, 'placeholder': 'Nombre del titular'},
            {'nombre': 'alias', 'label': 'Alias (opcional)', 'tipo': 'text', 'maxlength': 50, 'placeholder': 'mi.alias.mp', 'requerido': False},
        ]

    def validar_datos(self, datos_pago: dict) -> dict:
        errores = []

        cbu_cvu = datos_pago.get('cbu_cvu', '').replace(' ', '').replace('-', '')
        if not cbu_cvu or len(cbu_cvu) != 22 or not cbu_cvu.isdigit():
            errores.append('El CBU/CVU debe tener 22 dígitos numéricos.')

        titular = datos_pago.get('titular_cuenta', '').strip()
        if not titular:
            errores.append('El titular de la cuenta es obligatorio.')

        return {'valido': len(errores) == 0, 'errores': errores}

    def procesar_pago(self, datos_pago: dict) -> dict:
        time.sleep(2)  # Simula latencia de API

        if random.random() < 0.03:
            return {
                'exito': False,
                'mensaje': 'No se pudo verificar la cuenta de origen. Intente nuevamente.',
                'comprobante': None,
                'detalle': {},
            }

        cbu_cvu = datos_pago.get('cbu_cvu', '').replace(' ', '').replace('-', '')
        comprobante = self._generar_comprobante('TRX-TF')

        return {
            'exito': True,
            'mensaje': 'Transferencia procesada exitosamente.',
            'comprobante': comprobante,
            'detalle': {
                'titular_cuenta': datos_pago.get('titular_cuenta', ''),
                'cbu_cvu_parcial': f'***{cbu_cvu[-4:]}' if len(cbu_cvu) >= 4 else '',
            },
        }


# 3. El Contexto
class ContextoPago:
    # Cuando se crea el contexto, se le asigna una estrategia concreta que va a usar.
    def __init__(self, estrategia: EstrategiaPago):
        self._estrategia = estrategia

    # Permite que se cambie la estrategia en tiempo de ejecución, si el usuario decide cambiar su método de pago después de haber seleccionado uno inicialmente.
    def set_estrategia(self, estrategia: EstrategiaPago):
        self._estrategia = estrategia

    # Ejecuta el método de cálculo dependiendo de la estrategia concreta que se le asignó.
    def ejecutar_estrategia(self, monto_base: Decimal) -> Decimal:
        return self._estrategia.calcular_total(monto_base)

    def validar_datos(self, datos_pago: dict) -> dict:
        return self._estrategia.validar_datos(datos_pago)

    def procesar_pago(self, datos_pago: dict) -> dict:
        return self._estrategia.procesar_pago(datos_pago)

    def obtener_campos_requeridos(self) -> list:
        return self._estrategia.obtener_campos_requeridos()


def _normalizar_texto(texto: str) -> str:
    texto_normalizado = unicodedata.normalize('NFD', texto or '') # Borra acentos.
    texto_sin_acentos = ''.join(
        caracter for caracter in texto_normalizado if unicodedata.category(caracter) != 'Mn'
    )
    return texto_sin_acentos.casefold().strip() # Transforma a minúsculas y borra espacios


_ESTRATEGIAS_POR_METODO = {
    _normalizar_texto('Tarjeta de crédito'): EstrategiaTarjetaCredito(),
    _normalizar_texto('Tarjeta de débito'): EstrategiaTarjetaDebito(),
    _normalizar_texto('Transferencia'): EstrategiaTransferencia(),
}


def obtener_estrategia_pago(nombre_metodo_pago: str) -> EstrategiaPago:
    estrategia = _ESTRATEGIAS_POR_METODO.get(_normalizar_texto(nombre_metodo_pago))
    if estrategia is None:
        raise ValueError('Debes seleccionar un metodo de pago valido.')
    return estrategia