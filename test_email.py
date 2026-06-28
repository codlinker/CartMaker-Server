import smtplib

try:
    server = smtplib.SMTP('mail.privateemail.com', 587)
    server.set_debuglevel(1) # Esto imprimirá toda la traza técnica
    server.starttls()
    server.login('contact@cartmaker.app', 'Asia_27.')
    print("¡Conexión exitosa!")
    server.quit()
except Exception as e:
    print(f"Falló: {e}")