#!/usr/bin/env bash
# Copia de seguridad de tensión + recetas: base de datos PostgreSQL y ficheros media.
#
# - BD: pg_dump en formato custom (-Fc), comprimido y verificado con pg_restore --list.
# - Media: instantáneas diarias con rsync --link-dest (cada día es una copia completa
#   navegable, pero los ficheros sin cambios son hardlinks y no ocupan espacio extra).
# - Rotación: se conservan BACKUP_KEEP_DAYS días.
# - Copia externa opcional con rclone (muy recomendable: una copia solo en el
#   VPS no sobrevive a la pérdida del VPS).
#
# Configuración: /etc/tension/backup.env (ver backup.env.example)
# Uso: backup.sh [ruta_config]

set -Eeuo pipefail
umask 077

CONFIG_FILE="${1:-/etc/tension/backup.env}"
if [[ ! -r "$CONFIG_FILE" ]]; then
    echo "ERROR: no se puede leer la configuración $CONFIG_FILE" >&2
    exit 1
fi
# shellcheck source=/dev/null
source "$CONFIG_FILE"

: "${DATABASE_URL:?DATABASE_URL no definido}"
: "${MEDIA_ROOT:?MEDIA_ROOT no definido}"
: "${BACKUP_DIR:?BACKUP_DIR no definido}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
RCLONE_REMOTE="${RCLONE_REMOTE:-}"
ENV_FILE="${ENV_FILE:-}"

log() { echo "[$(date '+%F %T')] $*"; }
trap 'log "ERROR en la línea $LINENO: la copia NO se ha completado"' ERR

mkdir -p "$BACKUP_DIR"

# Evitar ejecuciones solapadas
exec 9>"${BACKUP_DIR}/.backup.lock"
if ! flock -n 9; then
    log "Ya hay una copia en curso; salgo."
    exit 0
fi

STAMP="$(date '+%Y%m%d_%H%M%S')"
DB_DIR="${BACKUP_DIR}/db"
MEDIA_DIR="${BACKUP_DIR}/media"
CONF_DIR="${BACKUP_DIR}/config"
mkdir -p "$DB_DIR" "$MEDIA_DIR" "$CONF_DIR"

# ── 1. Base de datos ───────────────────────────────────────────────────────
# libpq acepta tanto postgres:// como postgresql://
DUMP_FILE="${DB_DIR}/tension_${STAMP}.dump"
log "Volcando base de datos → ${DUMP_FILE}"
pg_dump --format=custom --compress=9 --no-owner --no-privileges \
    --file="${DUMP_FILE}.partial" "$DATABASE_URL"
pg_restore --list "${DUMP_FILE}.partial" > /dev/null   # verificación de integridad
mv "${DUMP_FILE}.partial" "$DUMP_FILE"
log "BD OK ($(du -h "$DUMP_FILE" | cut -f1))"

# ── 2. Ficheros media (instantánea incremental) ────────────────────────────
SNAPSHOT="${MEDIA_DIR}/${STAMP}"
LATEST="${MEDIA_DIR}/latest"
log "Instantánea de media ${MEDIA_ROOT} → ${SNAPSHOT}"
if [[ -d "$MEDIA_ROOT" ]]; then
    LINK_DEST=()
    if [[ -d "$LATEST" ]]; then
        LINK_DEST=(--link-dest="$(readlink -f "$LATEST")")
    fi
    rsync -a --delete "${LINK_DEST[@]}" "${MEDIA_ROOT%/}/" "${SNAPSHOT}.partial/"
    mv "${SNAPSHOT}.partial" "$SNAPSHOT"
    ln -sfn "$SNAPSHOT" "$LATEST"
    log "Media OK ($(find "$SNAPSHOT" -type f | wc -l) ficheros)"
else
    log "AVISO: MEDIA_ROOT ${MEDIA_ROOT} no existe todavía; se omite."
fi

# ── 3. Configuración (.env con secretos, permisos 600) ─────────────────────
if [[ -n "$ENV_FILE" && -r "$ENV_FILE" ]]; then
    cp "$ENV_FILE" "${CONF_DIR}/env_${STAMP}"
    chmod 600 "${CONF_DIR}/env_${STAMP}"
    log "Configuración OK"
fi

# ── 4. Rotación ────────────────────────────────────────────────────────────
log "Eliminando copias de más de ${BACKUP_KEEP_DAYS} días"
find "$DB_DIR" -maxdepth 1 -name 'tension_*.dump' -mtime +"$BACKUP_KEEP_DAYS" -delete
find "$DB_DIR" -maxdepth 1 -name '*.partial' -mmin +120 -delete
find "$CONF_DIR" -maxdepth 1 -name 'env_*' -mtime +"$BACKUP_KEEP_DAYS" -delete
find "$MEDIA_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +"$BACKUP_KEEP_DAYS" \
    ! -path "$(readlink -f "$LATEST" 2>/dev/null || echo /nonexistent)" -exec rm -rf {} +

# ── 5. Copia externa (opcional) ────────────────────────────────────────────
if [[ -n "$RCLONE_REMOTE" ]]; then
    log "Sincronizando con ${RCLONE_REMOTE}"
    rclone sync "${DB_DIR}" "${RCLONE_REMOTE}/db" --quiet
    if [[ -d "$LATEST" ]]; then
        rclone sync "$(readlink -f "$LATEST")/" "${RCLONE_REMOTE}/media" --quiet
    fi
    if [[ -n "$ENV_FILE" ]]; then
        rclone sync "${CONF_DIR}" "${RCLONE_REMOTE}/config" --quiet
    fi
    log "Copia externa OK"
fi

log "Copia de seguridad completada"
