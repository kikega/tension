# Despliegue — Fase 0: recetas.egalvez.es

Un único proyecto Django sirve **tension.egalvez.es** y **recetas.egalvez.es**.
`config.middleware.HostRoutingMiddleware` elige el urlconf según el host:

| Host | URLconf |
|---|---|
| `recetas.egalvez.es` (`RECETAS_HOST`) | `config/urls_recetas.py` |
| `recetas.localhost` (desarrollo) | `config/urls_recetas.py` |
| cualquier otro permitido | `config/urls.py` (tensión) |

## 1. Variables nuevas en el `.env` de producción

```dotenv
ALLOWED_HOSTS=tension.egalvez.es,recetas.egalvez.es
TENSION_HOST=tension.egalvez.es
RECETAS_HOST=recetas.egalvez.es
MEDIA_ROOT=/var/www/tension/media
```

En desarrollo añade `recetas.localhost` a `ALLOWED_HOSTS` y abre
<http://recetas.localhost:8000/> (los navegadores resuelven `*.localhost` a 127.0.0.1).

## 2. Código y dependencias

```bash
cd /var/www/tension
git pull
uv sync --group prod          # instala Pillow
uv run python manage.py check --deploy --settings=config.settings.produccion
uv run python manage.py collectstatic --noinput --settings=config.settings.produccion
```

## 3. Directorio media (AlmaLinux 9/10 con SELinux)

```bash
sudo mkdir -p /var/www/tension/media
sudo chown tension:nginx /var/www/tension/media        # usuario de gunicorn : grupo de nginx
sudo chmod 2775 /var/www/tension/media                 # setgid: los ficheros nuevos heredan el grupo nginx

# Nginx solo lee; Django (gunicorn) escribe
sudo semanage fcontext -a -t httpd_sys_rw_content_t "/var/www/tension/media(/.*)?"
sudo restorecon -Rv /var/www/tension/media
```

> Si gunicorn corre fuera del dominio `httpd_t` (lo normal con systemd), basta con
> que nginx pueda leer (`httpd_sys_rw_content_t` incluye lectura). Revisa
> `ausearch -m avc -ts recent` si aparece un 403 al servir `/media/`.

## 4. Nginx

```bash
sudo cp deploy/nginx/recetas.egalvez.es.conf /etc/nginx/conf.d/
sudo vi /etc/nginx/conf.d/recetas.egalvez.es.conf   # ajustar upstream, certificados y rutas
sudo nginx -t && sudo systemctl reload nginx
```

- El certificado wildcard `*.egalvez.es` ya cubre el subdominio.
- DNS: el registro `*.egalvez.es` (o un `A/AAAA recetas`) debe apuntar al VPS.
- Recomendado: añadir también al vhost de tensión el bloque `location /media/` con
  el `deny` de HTML/SVG/scripts, para que la protección sea la misma en los dos hosts.
- Comprobación: `curl -I https://recetas.egalvez.es/` → 200 y la página «Próximamente».

## 5. Copias de seguridad

| Qué | Cómo | Retención |
|---|---|---|
| PostgreSQL | `pg_dump -Fc` + verificación con `pg_restore --list` | `BACKUP_KEEP_DAYS` (14) |
| Media | Instantánea diaria con `rsync --link-dest` (incremental con hardlinks) | `BACKUP_KEEP_DAYS` |
| `.env` | Copia con permisos 600 (opcional) | `BACKUP_KEEP_DAYS` |
| Externa | `rclone sync` a un remoto (opcional, **recomendado**) | la del remoto |

```bash
sudo mkdir -p /etc/tension /var/backups/tension
sudo cp deploy/backup/backup.env.example /etc/tension/backup.env
sudo chmod 600 /etc/tension/backup.env && sudo chown tension: /etc/tension/backup.env
sudo chown tension: /var/backups/tension
sudo vi /etc/tension/backup.env

# Prueba manual
sudo -u tension /var/www/tension/deploy/backup/backup.sh

# Programación diaria (03:30)
sudo cp deploy/backup/tension-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tension-backup.timer
systemctl list-timers tension-backup.timer
journalctl -u tension-backup.service -n 50
```

Necesita `pg_dump` con la **misma versión mayor** (o superior) que el servidor
PostgreSQL, además de `rsync` y, opcionalmente, `rclone`.

### Restauración

```bash
sudo systemctl stop <servicio-gunicorn>
sudo -u tension deploy/backup/restore.sh db    /var/backups/tension/db/tension_YYYYmmdd_HHMMSS.dump
sudo -u tension deploy/backup/restore.sh media /var/backups/tension/media/YYYYmmdd_HHMMSS
sudo systemctl start <servicio-gunicorn>
```

> Prueba una restauración completa en una BD de pruebas al menos una vez:
> una copia que no se ha probado no es una copia.

## 6. Migración a AlmaLinux 10

Nada de esta fase depende de la versión: nginx, systemd, SELinux (`semanage`
viene en `policycoreutils-python-utils`), rsync y uv funcionan igual. Tras la
actualización, revisa que el paquete cliente de PostgreSQL coincida con la
versión del servidor (para `pg_dump`) y vuelve a ejecutar `restorecon` sobre
`media/`.

---

# Despliegue — Fase 1: app `recipes`, SSO y migraciones versionadas

A partir de esta fase:
- Las migraciones entran en git (se ha quitado `migrations/` de `.gitignore`).
- `Recipe` y `RecipeIngredient` viven en la app `recipes`, conservando las
  tablas existentes `nutrition_recipe` y `nutrition_recipeingredient` mediante
  `SeparateDatabaseAndState` (sin mover ni borrar datos).
- La sesión y la cookie CSRF se comparten entre subdominios con
  `SESSION_COOKIE_DOMAIN=.egalvez.es` y `CSRF_COOKIE_DOMAIN=.egalvez.es`
  (por defecto en `config/settings/produccion.py`).
- `tension.egalvez.es/nutrition/recipes/...` devuelve 301 permanente hacia
  `recetas.egalvez.es/...`.

## Pasos en producción (con BD existente con datos)

1. **Copia de seguridad previa obligatoria:**

```bash
sudo -u tension /var/www/tension/deploy/backup/backup.sh
```

2. **Actualizar código y limpiar el historial antiguo de migraciones:**
   Como antes `migrations/` no estaba en git, las migraciones intermedias
   generadas localmente en el servidor (`0002_*`, `0003_*`, …) ya están
   consolidadas en el nuevo `0001_initial.py` de `accounts`, `nutrition` y
   `tracking`. Hay que borrar cualquier fichero antiguo de `*/migrations/` que
   no venga en git y podar esas entradas de `django_migrations`:

```bash
cd /var/www/tension
git pull
# Eliminar ficheros de migraciones antiguas que estuvieran sin versionar en el VPS
git clean -fd accounts/migrations nutrition/migrations tracking/migrations

# Podar en django_migrations las entradas antiguas que ya no existen en disco
uv run python manage.py migrate accounts  --prune --settings=config.settings.produccion
uv run python manage.py migrate nutrition --prune --settings=config.settings.produccion
uv run python manage.py migrate tracking  --prune --settings=config.settings.produccion

# Aplicar las migraciones de la Fase 1 (solo estado + ContentType; 0 cambios de esquema)
uv run python manage.py migrate --settings=config.settings.produccion
```

3. **Comprobar y reiniciar:**

```bash
uv run python manage.py showmigrations accounts nutrition recipes tracking --settings=config.settings.produccion
uv run python manage.py check --deploy --settings=config.settings.produccion
uv run python manage.py collectstatic --noinput --settings=config.settings.produccion
sudo systemctl restart <servicio-gunicorn>
```

4. **Verificación rápida:**
   - `curl -I https://tension.egalvez.es/nutrition/recipes/` → `301` hacia `https://recetas.egalvez.es/`.
   - Iniciar sesión en `https://tension.egalvez.es/` y abrir `https://recetas.egalvez.es/` → entras ya autenticado (SSO) viendo tus recetas.
   - Registrar una ingesta con receta en `tension.egalvez.es` → sigue funcionando igual.

