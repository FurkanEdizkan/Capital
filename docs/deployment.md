# Deploying Capital

Capital runs as a Docker Compose stack — `postgres`, `engine`, `web` and a
`caddy` reverse proxy that is the single entry point. There are two supported
deployments:

- **Private (Tailscale / LAN)** — the original model: the dashboard is reached
  over a private network, TLS via Caddy's internal CA. No public exposure.
- **Cloud VM** — a server reachable on a real domain over the public internet,
  TLS via Let's Encrypt.

Both use the same images and compose files; only a few `.env` values differ.

## Common steps

1. Install Docker Engine + the Compose plugin on the host.
2. Clone the repo (e.g. into `/opt/capital`).
3. `cp .env.example .env` and set, at minimum:
   - `CAPITAL_JWT_SECRET`, `CAPITAL_SECRET_KEY` — long random strings.
   - `CAPITAL_ADMIN_PASSWORD` — changed again after first login.
   - `POSTGRES_PASSWORD`.
   - `CAPITAL_ENVIRONMENT=production`.
4. Deploy: `make deploy` (builds images, applies migrations, starts the stack,
   polls the health endpoint). Re-run it to update.
5. Optional: install the `capital.service` systemd unit so the stack starts on
   boot — it runs from `/opt/capital`; adjust `WorkingDirectory` if you cloned
   elsewhere.

`CAPITAL_SECRET_KEY` encrypts the stored venue/LLM API keys. Back it up
**separately** from the database — see [backup-and-restore.md](backup-and-restore.md).

## Private deployment (Tailscale)

1. Install Tailscale on the host and join your tailnet.
2. In `.env`:
   - `CAPITAL_HOSTNAME` = the host's MagicDNS name (e.g. `capital.tail1234.ts.net`).
   - `TAILSCALE_HOST` = the host's Tailscale IP (`100.x.y.z`) — Caddy binds
     only there, so nothing is exposed to the public internet.
   - `CAPITAL_TLS=internal`.
3. `make deploy`. The dashboard is `https://<MagicDNS-name>` from any device on
   the tailnet. Browsers will warn about Caddy's internal CA — expected.

## Cloud VM deployment (public domain)

1. Provision a small Linux VM and point a domain's DNS **A record** at its
   public IP.
2. **Firewall** — allow inbound **80** and **443** only; block **5432**
   (Postgres), **8000** (engine) and **5173** (web). The prod compose already
   gives those services no host ports, but a host firewall (ufw / cloud
   security group) is the backstop.
3. In `.env`:
   - `CAPITAL_HOSTNAME` = your domain (e.g. `capital.example.com`).
   - `TAILSCALE_HOST=0.0.0.0` — Caddy listens on all interfaces.
   - `CAPITAL_TLS=you@example.com` — Caddy obtains a Let's Encrypt certificate
     for the domain automatically (port 80 must be reachable for the ACME
     challenge).
4. `make deploy`. The dashboard is `https://<your-domain>` with a valid
   public certificate; HTTP is redirected to HTTPS.

## Notes

- The engine reaches its venues (Binance, etc.) outbound — if a venue is
  geo-restricted, host the VM where it is reachable, or route through a VPN on
  the host. Capital itself has no jurisdiction logic.
- Caddy sends HSTS and other hardening headers on every response. The login
  endpoint is rate-limited in the engine itself.
- Back up the database off the VM (e.g. object storage) — `scripts/backup.sh`
  writes to `data/backups/`; copy those off-box on a schedule.
- After any deploy, check `make logs` and the dashboard's watchdog status.
