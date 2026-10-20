# OSRM Local Nativo (Venezuela, MLD, `--mmap`)

Infraestructura local de enrutamiento para CartMaker sobre el extracto de Venezuela de Geofabrik, ejecutada nativamente con `systemd`.

## Arquitectura en Instancias EC2 Micro (1 GB RAM)
`rebuild.sh` descarga directamente los binarios C++ precompilados de OSRM v5.27.1 en `/opt/osrm/rootfs` usando únicamente `curl`, `python3` y `tar`, y registra el motor como un servicio nativo de Linux (`osrm-car.service`) con `--mmap` (~80–120 MB de RAM).

## Puertos (solo loopback `127.0.0.1`)
- `127.0.0.1:5000` — servicio `osrm-car.service` (perfil `car`, usado para carro, moto y fallback de bici/pie)
- `127.0.0.1:5001` — servicio `osrm-bike.service` (opcional, si se ejecuta `BUILD_BIKE=1 ./rebuild.sh`)

## Instalación y actualización en un solo paso

```bash
cd scripts/osrm
chmod +x rebuild.sh
./rebuild.sh
```

El script:
1. Verifica que haya suficiente RAM + Swap (crea `/swapfile` de 4 GB automáticamente si hace falta).
2. Descarga los binarios precompilados de OSRM v5.27.1 en `/opt/osrm/rootfs`.
3. Descarga `venezuela-latest.osm.pbf` y valida su MD5.
4. Ejecuta `osrm-extract`, `osrm-partition` y `osrm-customize` de forma atómica.
5. Crea y arranca `/etc/systemd/system/osrm-car.service` con `--mmap` y verifica con un `curl` de prueba que `http://127.0.0.1:5000` responda.

## Comandos útiles de `systemd`
```bash
sudo systemctl status osrm-car
sudo journalctl -u osrm-car -f
sudo systemctl restart osrm-car
```

## Prueba rápida
```bash
curl 'http://127.0.0.1:5000/route/v1/driving/-66.9036,10.4806;-66.8520,10.4910?overview=full&geometries=polyline6&annotations=duration,distance'
```
