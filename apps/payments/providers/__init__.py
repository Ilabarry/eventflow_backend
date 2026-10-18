"""
Package des providers de paiement EVENTFLOW.

Chaque provider est une classe qui implémente l'interface
AbstractPaymentProvider. Le PaymentService utilise la factory
get_provider() pour récupérer le provider souhaité.
"""

from apps.payments.providers.factory import get_provider

__all__ = ["get_provider"]