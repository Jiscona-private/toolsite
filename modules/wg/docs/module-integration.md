# Einbindung in die Toolsite

Die WG-App ist ein Modul der Toolsite (`/README.md`, `/docs/ADDING_MODULES.md`) und ersetzt das Dummy-Modul `modules/wg-manager`. Die Toolsite läuft bereits mit Domain auf dem netcup VPS piko (Setup: `/docs/SETUP.md`).

## Modul-Vertrag

| Punkt | WG-App |
| --- | --- |
| Verzeichnis | `modules/wg/` |
| Service-Name | `wg` |
| Port | `PORT=3000`, nur intern im Netz `toolsite_net` |
| Pfad | `BASE_PATH=/wg`, Caddy `handle /wg*` (Präfix bleibt erhalten) |
| Daten | `modules/wg/data/` → im Container `/data` (`DATABASE_PATH=/data/wg.db`, `BACKUP_DIR=/data/backups`) |
| Landing-Page | `module.json`: `{"id": "wg", "name": "WG", "description": "Putzplan, Ausgaben und Einkauf für unsere WG", "path": "/wg/", "icon": "🏠"}` |
| Zugang | geheimer Link `https://<DOMAIN>/wg/join/<token>`, **keine** Basic Auth |

## `modules/wg/compose.yaml` (Ziel)

```yaml
services:
  wg:
    build: .
    restart: unless-stopped
    volumes:
      - ./data:/data
    environment:
      - PORT=3000
      - BASE_PATH=/wg
      - APP_ENV=prod
      - APP_BASE_URL=https://${DOMAIN}/wg
      - SECRET_KEY=${WG_SECRET_KEY}
      - DATABASE_PATH=/data/wg.db
      - BACKUP_DIR=/data/backups
      - NTFY_BASE_URL=https://ntfy.sh
      - TZ=Europe/Berlin
    networks:
      - toolsite_net

networks:
  toolsite_net:
    name: toolsite_net
```

Keine `ports:`, kein `external: true` beim Netz (siehe `/docs/ADDING_MODULES.md`).

## Umstieg vom Dummy (letzter Schritt von Phase 1, ein PR)

1. `/docker-compose.yml`: `modules/wg-manager/compose.yaml` → `modules/wg/compose.yaml`. Beim `caddy`-Service `WG_BASIC_AUTH_USER`/`WG_BASIC_AUTH_HASH` entfernen.
2. `/Caddyfile`: den `/wg*`-Block ersetzen durch
   ```
   handle /wg* {
   	reverse_proxy wg:3000
   }
   ```
3. `/.env.example`: `WG_BASIC_AUTH_*` entfernen, `WG_SECRET_KEY=` mit Hinweis `python3 -c "import secrets; print(secrets.token_hex(32))"` ergänzen.
4. `modules/wg/module.json` anlegen, `modules/wg-manager/` löschen.
5. `/README.md` und `/docs/SETUP.md` (Abschnitt Basic Auth) anpassen.

## Auf dem Server (macht der Projektinhaber)

```bash
cd /opt/toolsite
./scripts/backup.sh                    # sichert auch die alten Dummy-Daten
nano .env                              # WG_SECRET_KEY eintragen, WG_BASIC_AUTH_* kann weg
./scripts/deploy.sh                    # --remove-orphans entfernt den alten wg-manager-Container
docker compose exec wg python -m app.cli init --seed deploy/seed.toml   # gibt den Beitrittslink aus
```
Danach `https://<DOMAIN>/wg/` ohne Link öffnen → „Not Found“ (richtig so). Mit dem Link → „Wer bist du?“.
