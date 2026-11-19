#!/usr/bin/env bash
# Restauración de una copia de seguridad (BD y/o media).
#
# Uso:
#   restore.sh db    /ruta/backups/db/tension_YYYYmmdd_HHMMSS.dump [ruta_config]
#   restore.sh media /ruta/backups/media/YYYYmmdd_HHMMSS            [ruta_config]
#
# ATENCIÓN: sobrescribe los datos actuales. Para la app antes de restaurar:
#   systemctl stop <servicio-gunicorn>

set -Eeuo pipefail

MODE="${1:-}"
SOURCE="${2:-}"
CONFIG_FILE="${3:-/etc/tension/backup.env}"

if [[ -z "$MODE" || -z "$SOURCE" ]]; then
    sed -n '2,10p' "$0"
    exit 1
fi
# shellcheck source=/dev/null
source "$CONFIG_FILE"

confirm() {
    read -r -p "$1 Escribe 'SI' para continuar: " answer
    [[ "$answer" == "SI" ]] || { echo "Cancelado."; exit 1; }
}

case "$MODE" in
    db)
        : "${DATABASE_URL:?DATABASE_URL no definido}"
        pg_restore --list "$SOURCE" > /dev/null
        confirm "Se van a SOBRESCRIBIR las tablas de la BD con ${SOURCE}."
        pg_restore --clean --if-exists --no-owner --no-privileges \
            --single-transaction --dbname="$DATABASE_URL" "$SOURCE"
        echo "BD restaurada."
        ;;
    media)
        : "${MEDIA_ROOT:?MEDIA_ROOT no definido}"
        [[ -d "$SOURCE" ]] || { echo "No existe ${SOURCE}" >&2; exit 1; }
        confirm "Se va a SINCRONIZAR ${MEDIA_ROOT} con ${SOURCE} (se borrarán ficheros que no estén en la copia)."
        rsync -a --delete "${SOURCE%/}/" "${MEDIA_ROOT%/}/"
        if command -v restorecon > /dev/null; then
            restorecon -R "$MEDIA_ROOT"
        fi
        echo "Media restaurada."
        ;;
    *)
        echo "Modo desconocido: ${MODE} (usa 'db' o 'media')" >&2
        exit 1
        ;;
esac
