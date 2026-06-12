import os
import sys
from django.apps import AppConfig
from django.core.cache import cache


class WebConfig(AppConfig):
    name = 'web'

    def ready(self):
        import web.signals
        valid_commands = ['runserver', 'gunicorn', 'daphne', 'uwsgi', 'uvicorn']
        is_valid_server = any(command in sys.argv[0] or any(command in arg for arg in sys.argv) for command in valid_commands)
        
        if is_valid_server:
            # 💡 Obtenemos el ID del proceso padre (El Master de Uvicorn)
            current_parent_pid = os.getppid()
            
            # Consultamos en caché cuál fue el último Master al que le limpiamos todo
            last_cleared_ppid = cache.get('CARTMAKER_MASTER_PID')
            
            if last_cleared_ppid != current_parent_pid:
                # Si no coinciden (o es None), significa que acabas de encender el 
                # servidor manualmente en la consola. ¡Fuego a discreción! 🔥
                cache.clear()
                
                # Inmediatamente después de limpiar, guardamos el ID del padre actual
                # para que los futuros reloads lo reconozcan y lo dejen quieto.
                cache.set('CARTMAKER_MASTER_PID', current_parent_pid, timeout=None)
                
                print("\n🧹 [CARTMAKER] Nuevo servidor detectado: ¡Caché global aniquilada con éxito!\n")
            else:
                # Si coinciden, significa que Uvicorn solo está recargando por un cambio de código (Ctrl+S)
                print("\n♻️ [CARTMAKER] Auto-Reload: Conservando caché y carritos actuales.\n")
