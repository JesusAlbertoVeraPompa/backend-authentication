# apps/core/utils.py

import random

def generate_verification_code():
    """
    Genera un código numérico de 6 dígitos para verificación.
    """
    return random.randint(100000, 999999)