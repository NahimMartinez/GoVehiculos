from abc import ABC, abstractmethod
from decimal import Decimal
import unicodedata

# 1. La Interfaz de la Estrategia
class EstrategiaPago(ABC):
    @abstractmethod
    def calcular_total(self, monto_base: Decimal) -> Decimal:
        """Calcula el monto final aplicando reglas específicas del método de pago."""
        pass

# 2. Estrategias Concretas
class EstrategiaTarjetaCredito(EstrategiaPago):
    def calcular_total(self, monto_base: Decimal) -> Decimal:
        # Aplica un 10% de recargo por uso de tarjeta de crédito
        recargo = monto_base * Decimal('0.10')
        return monto_base + recargo

class EstrategiaTarjetaDebito(EstrategiaPago):
    def calcular_total(self, monto_base: Decimal) -> Decimal:
        # La tarjeta de débito cobra el precio de lista (sin alteraciones)
        return monto_base

class EstrategiaTransferencia(EstrategiaPago):
    def calcular_total(self, monto_base: Decimal) -> Decimal:
        # Aplica un 5% de descuento por pago en transferencia
        descuento = monto_base * Decimal('0.05')
        return monto_base - descuento

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