import os
import smtplib

try:
    smtp_host = os.environ.get('EMAIL_HOST', 'mail.privateemail.com')
    smtp_port = int(os.environ.get('EMAIL_PORT', 587))
    smtp_user = os.environ.get('EMAIL_HOST_USER', '')
    smtp_pass = os.environ.get('EMAIL_HOST_PASSWORD', '')

    server = smtplib.SMTP(smtp_host, smtp_port)
    server.set_debuglevel(1)
    server.starttls()
    server.login(smtp_user, smtp_pass)
    print("¡Conexión exitosa!")
    server.quit()
except Exception as e:
    print(f"Falló: {e}")