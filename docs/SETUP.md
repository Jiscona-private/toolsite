# VPS setup

Step-by-step provisioning for a fresh netcup Pico VPS (or any small Debian/Ubuntu VPS).

## 0. Why you need a domain

A trusted HTTPS certificate (what browsers accept without warnings) is issued
by Let's Encrypt against a **domain name**, not a bare IPv4 address. You
cannot get a normal green-padlock cert for `http://203.0.113.5` directly.

The practical setup is: point a free or cheap domain/subdomain at your VPS's
IPv4 address, and use that domain everywhere. Options for a free hostname:

- [DuckDNS](https://www.duckdns.org/) — free subdomain like `yourname.duckdns.org`, update via a tiny script/cron so it always points at your VPS's current IP.
- A subdomain of a domain you already own (just add an `A` record).

Once you have a hostname, create an **A record** pointing it at your VPS's
IPv4 address. DNS propagation can take a few minutes.

## 1. Update the system and install Docker

SSH into the VPS as root (or a sudo user), then:

```bash
apt update && apt upgrade -y

# Official Docker install script (installs Docker Engine + Compose plugin)
curl -fsSL https://get.docker.com | sh

# Verify
docker --version
docker compose version   # must be v2.20+ for the `include:` feature this repo uses
```

If your distro ships an older Compose plugin, add Docker's own apt
repository per https://docs.docker.com/engine/install/debian/ instead of
relying on the distro package.

## 2. Firewall

Only SSH, HTTP, and HTTPS need to be open:

```bash
apt install -y ufw
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status
```

## 3. Clone the repo onto the VPS

```bash
git clone <this-repo-url> /opt/toolsite
cd /opt/toolsite
git checkout claude/netcup-vps-modular-setup-htbwer   # or your deploy branch
```

## 4. Configure environment

```bash
cp .env.example .env
nano .env
```

Fill in:

- `DOMAIN` — the hostname you pointed at the VPS (e.g. `yourname.duckdns.org`).
- `ACME_EMAIL` — your email, used only for Let's Encrypt expiry notices.
- `WG_SECRET_KEY` — signs WG-Manager v1's cookies and CSRF tokens:

  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```

## 5. First launch

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f caddy
```

The first request to your domain triggers Caddy to request a Let's Encrypt
certificate automatically — this can take 10-30 seconds. Watch the `caddy`
logs if it doesn't come up.

**Testing before you're sure DNS is right:** Let's Encrypt rate-limits
repeated failed attempts for the same domain. If you're unsure DNS has
propagated yet, temporarily add this to the top of `Caddyfile` while testing,
then remove it once things work:

```
{
	acme_ca https://acme-staging-v02.api.letsencrypt.org/directory
}
```

(Staging certs aren't trusted by browsers, but let you verify the whole
pipeline works without burning your production rate limit.)

## 6. Visit the site

Open `https://<your-domain>/` — you should see the Toolsite landing page
listing installed modules. `https://<your-domain>/wg/` without a join link
is a plain "Not Found" by design (see `modules/wg/CLAUDE.md`); run
`docker compose exec wg python -m app.cli init --seed deploy/seed.toml`
once to seed the household and print that link.

## Ongoing operations

- **Deploy updates:** `scripts/deploy.sh` (git pull, rebuild, restart).
- **Backups:** `scripts/backup.sh` tars up every module's `data/` directory
  into `backups/`. Add it to cron, e.g. daily at 03:00:
  ```bash
  crontab -e
  # 0 3 * * * /opt/toolsite/scripts/backup.sh >> /var/log/toolsite-backup.log 2>&1
  ```
- **Add a new tool:** see `docs/ADDING_MODULES.md`.
- **Logs:** `docker compose logs -f <service>` (e.g. `caddy`, `landing`, `wg`).

## Resource notes for a Pico-tier VPS

This stack is intentionally light: Caddy (~20-30 MB RAM), the landing page
(a few MB, no build step), and each module as a small single process with
SQLite (file-based, no separate database server to run). Keep that pattern
for new modules — avoid adding a full database server (Postgres/MySQL)
unless you've checked the VPS has RAM to spare; SQLite covers nearly
everything a small personal-tools site needs.
