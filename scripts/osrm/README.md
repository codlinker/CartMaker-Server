# OSRM propio (rutas de CartMaker Delivery)

Dos instancias de [OSRM](https://github.com/Project-OSRM/osrm-backend) en Docker, escuchando **solo en `127.0.0.1`**:

| Puerto | Perfil | Vehículos | Setting de Django |
|---|---|---|---|
| `5000` | `car.lua` | moto y carro | `OSRM_CAR_URL` (por defecto `http://127.0.0.1:5000`) |
| `5001` | `bicycle.lua` | bicicleta y a pie | `OSRM_BIKE_URL` (por defecto `http://127.0.0.1:5001`) |

Django las consume con `api/core/routing.py` (`route`, `table`, `match`).

## Primera instalación

```bash
cd scripts/osrm
chmod +x rebuild.sh
./rebuild.sh          # descarga venezuela-latest.osm.pbf, preprocesa (MLD) y levanta los contenedores
```

## Optimizado para AWS EC2 Micro (1 GB de RAM)

1. **Modo 0 MB de RAM extra (Sin Docker):**
   - Si no ejecutas `./rebuild.sh` ni prendes Docker en tu EC2 Micro, `api/core/routing.py` usa automáticamente **Mapbox Directions API** (`settings.MAPBOX_APIKEY`) y cálculo geodésico como respaldo. Todo el sistema de delivery funciona al 100% sin consumir RAM adicional.
2. **Modo OSRM propio en EC2 Micro (`--mmap` + Swap automático):**
   - `./rebuild.sh` detecta si la instancia tiene poca RAM y crea automáticamente un `/swapfile` de 4 GB en el disco SSD para que `osrm-extract` no se quede sin memoria al compilar el mapa.
   - En ejecución, `docker-compose.yml` usa `osrm-routed --algorithm mld --mmap` y levanta por defecto solo el contenedor `osrm-car` (`:5000`), consumiendo apenas **~80–120 MB de RAM**.
   - Si en el futuro pasas a una instancia más grande y quieres también el contenedor dedicado de bicicletas (`:5001`), corre `BUILD_BIKE=1 ./rebuild.sh` y `docker compose --profile full up -d`.

## Actualizar el mapa

```bash
./rebuild.sh            # solo reprocesa si Geofabrik publicó un extracto nuevo
FORCE=1 ./rebuild.sh    # reprocesa siempre
```

El script construye en `data/<perfil>.new/` y cambia los datos al final: si algo falla, los contenedores siguen sirviendo el mapa anterior. Se puede programar mensualmente (cron o Celery Beat).

## Comprobar que responde

```bash
curl "http://127.0.0.1:5000/route/v1/driving/-66.9036,10.4806;-66.8792,10.4961?overview=false"
curl "http://127.0.0.1:5001/route/v1/driving/-66.9036,10.4806;-66.8792,10.4961?overview=false"
```

## Variables opcionales

- `OSRM_CAR_URL`, `OSRM_BIKE_URL`, `OSRM_TIMEOUT_SECONDS` en `variables.sh` (Django).
- `OSRM_DATA_DIR`, `OSRM_PBF_URL`, `OSRM_IMAGE`, `FORCE`, `SKIP_RESTART` para `rebuild.sh`.

> La carpeta `data/` contiene archivos pesados generados: no se versiona en git.
