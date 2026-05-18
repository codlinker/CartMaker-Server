from google import genai
from django.conf import settings
import os

# Inicializa el cliente con tu clave
client = genai.Client(api_key="AIzaSyCM1K6IYNx4Mpz3rUbBWJnuaHKHD8i4Bug")

# Listamos todos los modelos disponibles en tu cuenta
print("Buscando modelos disponibles...")
for model in client.models.list():
    if "flash" in model.name.lower():
        print(f"-> ID para código: '{model.name}' ({model.display_name})")