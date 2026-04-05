from django.core.cache import cache
import random

def send_email_otp(user_email) -> str:
    """
    Genera el otp para el correo del usuario.

    Returns:
        otp_code(str): Codigo de verificacion de email.
    """
    otp_code = str(random.randint(10000, 99999))
    cache_key = f"otp_verification_{user_email}"
    cache.set(cache_key, otp_code, timeout=60)
    print(f"OTP CODE GENERADO PARA EL CORREO {user_email}: ", otp_code)
    return otp_code

def get_email_otp(user_email) -> str:
    """
    Obtiene el otp generado para el correo del usuario si es que existe.

    Returns:
        otp_code(str): Codigo de verificacion de email.
    """
    cache_key = f"otp_verification_{user_email}"
    return cache.get(cache_key)