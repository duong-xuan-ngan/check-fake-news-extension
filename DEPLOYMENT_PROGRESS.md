# AWS Deployment Progress — VeriFact (check-fake-news-extension)

## Context
Deploying backend (Docker Compose: postgres, redis, qdrant, backend, de-api) to AWS EC2 for real-user testing. Ngan is learning DevOps deliberately (chose AWS over Railway for this reason, has $200 AWS credit). Code lives in `phucnhan` branch, not `main`. Repo: `https://github.com/duong-xuan-ngan/check-fake-news-extension.git`.

## Completed

**AWS account setup**
- IAM user `ngan-admin` created (AdministratorAccess), access key saved
- MFA enabled on root
- Billing budget: $20/month alert to duongxuanngan.1102@gmail.com
- ⚠️ UNRESOLVED FLAG: a `rootkey.csv` was seen sitting in `~/.../Tech_Startup_Lab/VeriFact/` (iCloud-synced folder), never confirmed/denied by Ngan whether it's a real root access key. If real, root should have **zero** active access keys — delete it via IAM → root user → security credentials. Also flagged: `.pem` and IAM credential CSV living in iCloud sync is not ideal long-term (works, not best practice).
- ⚠️ NEW FLAG: a **second, unexplained EC2 instance** (`52.220.34.233`, `ap-southeast-1a`, 3/3 checks passed) was spotted alongside the intended one (`52.74.41.175`) while checking status checks. Not part of any deploy work in this project's sessions — never confirmed whether this is intentional (e.g. Phuc Nhan's own instance) or an orphaned/forgotten resource that's quietly costing money. Worth checking before next billing cycle.

**EC2 instance**
- Launched: `i-0fe1480ccbbdd87a`, Ubuntu 24.04, `t3.small`, 20GiB gp3, region `ap-southeast-1`
- Key pair: `verifact-key.pem`, stored at `/Users/duongxuanngan/Library/Mobile Documents/com~apple~CloudDocs/Documents/Tech_Startup_Lab/VeriFact/verifact-key.pem` (iCloud path — must `cd` there or use full path for SSH)
- Security group: SSH (22) restricted to Ngan's IP only, HTTP (80) + HTTPS (443) open to `0.0.0.0/0`. **Port 8000/8001 deliberately never opened publicly** — only Caddy is meant to be internet-facing.
- Elastic IP allocated + associated: **52.74.41.175**
- Docker + Docker Compose plugin installed on instance (`docker compose`, no hyphen). Required `sudo usermod -aG docker ubuntu` + fresh SSH session to take effect.
- **Known recurring friction**: SSH port 22 is allowlisted to Ngan's home IP specifically (`X.X.X.X/32`), which is a *dynamic* IP that changes periodically (ISP-side DHCP lease rotation, router restarts, network switches — nothing Ngan does wrong). When SSH times out with no other symptoms (instance shows 3/3 healthy in console), this is almost always the cause, not a server problem. **Fix**: EC2 console → instance → Security tab → security group → Edit inbound rules → SSH row → Source → "My IP" (auto-detects current IP) → Save. Takes effect instantly, no reboot. Already recurred once (confirmed: old rule had `171.251.232.107/32`, actual current IP was `171.236.48.243`). If this keeps recurring, consider switching to AWS Systems Manager Session Manager instead of SSH (no IP dependency) — not urgent yet.

**Code changes made (on Ngan's Mac, pushed to `origin/phucnhan`)**
1. `sidepanel-src/src/components/PopupApp.jsx` line 4:
   `const API_BASE = 'http://localhost:8000'` → `const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'`
2. `sidepanel-src/.env.production`: `VITE_API_BASE=https://verifact.duckdns.org` — done
3. `docker-compose.yml`: `backend` service changed from `ports: "8000:8000"` to `expose: "8000"` (internal-only now)
4. `docker-compose.yml`: added `caddy` service (image `caddy:2-alpine`, publishes 80/443, mounts `./Caddyfile`, volumes `caddy_data`/`caddy_config` for cert persistence)
5. `Caddyfile` created:
   ```
   verifact.duckdns.org {
       reverse_proxy backend:8000
   }
   ```
6. `extension/manifest.json` `host_permissions` — added `"https://verifact.duckdns.org/*"` alongside the existing `localhost:8000`/`127.0.0.1:8000` entries (kept for local dev). Done.

**DNS**
- DuckDNS domain created: `verifact.duckdns.org` → correctly points to Elastic IP `52.74.41.175`.

**First successful backend deploy (before Caddy was added)**
- All 5 original containers (postgres, redis, qdrant, backend, de-api) built and ran successfully, confirmed via `docker compose ps` + `curl` health checks + full `/analyze` pipeline test.

## Resolved: build failure (was a chain of 3 separate root causes, not 1)

The Caddy-triggered build failure took several rounds to fully resolve. Each fix was real and necessary — three independent problems, not retries of the same one:

1. **`uv` bytecode pre-compile timeout** — `ENV UV_COMPILE_BYTECODE=1` in `fn-extension-backend/Dockerfile` made `uv sync` pre-compile every installed file, with a 60s-per-file cap. Large PyTorch files exceeded that on `t3.small`'s CPU. **Fixed**: set `ENV UV_COMPILE_BYTECODE=0`. Committed `4a7f40e`.

2. **CUDA libs bundled despite CPU-only intent** — `uv.lock` predated the CPU-only torch index in `pyproject.toml`, so `--frozen` kept installing the CUDA build (~2GB of unusable `nvidia-*` packages). **Fixed**: ran `uv lock --upgrade-package torch`, confirmed `grep -c "nvidia-" uv.lock` → `0`. Image dropped from ~13GB to ~7GB. Committed `9de9bad`.

3. **No swap → OOM freeze under `t3.small`'s 2GB RAM** — compiling small pure-Python packages from source during `uv sync` pushed memory to the ceiling with nowhere to spill, freezing the entire instance (SSH timed out, EC2 health checks dropped to 2/3). **Fixed**: added a 4GB swapfile (`/swapfile`, persisted via `/etc/fstab`). Required an EC2 console reboot to recover the wedged instance first.

**Disk space is a recurring, ongoing constraint** (decided not to fix by growing disk):
- 19GB is tight: OS + 6 image layers (~7GB) + swapfile (4GB) + build cache.
- `docker compose up --build` builds the new image before removing the old one, so old+new must both fit momentarily — repeatedly caused "no space left on device."
- **Decision**: not growing the EBS volume (cost trade-off, explicitly declined). **Working pattern**: run `docker system prune -af` before every rebuild. Trade-off accepted: base images also get evicted, so every rebuild re-downloads them.

## Resolved: OpenRouter 402 → 401 → working key

After deployment succeeded, `/analyze` was returning `NOT_SURE` for every claim. Root cause chain (three distinct issues, each real):

1. **Original key ran out of credits** — every LLM call (`preprocessor`, `query_builder`, `synthesizer`) failed with `402: requires more credits`. This is why `NOT_SURE` appeared — it's the pipeline's correct fail-closed behavior when the LLM is unavailable, not a bug. **Fix**: got a new OpenRouter key.

2. **New key pasted with a space + surrounding quotes** in `.env` (`OPENROUTER_API_KEY= "sk-or-..."`) → caused `401: User not found`, because the literal quote characters were being sent as part of the key.

3. **Second attempt at fixing it manually mistyped/truncated the key** — ended in an invalid character (`...e9v`), which is structurally impossible for a real OpenRouter key (hex-only after the `sk-or-v1-` prefix). Also `401`.

4. **Final fix**: got a fresh key directly from `openrouter.ai/settings/keys`, pasted cleanly with no quotes and no space: `OPENROUTER_API_KEY=sk-or-v1-...` (no wrapping characters). **Confirmed working** — `docker compose logs backend` showed a full successful `/analyze` run with zero LLM errors (no `Translation failed`, no `LLM call failed`) for the first time.

**Lesson for future key rotations**: always paste directly from the provider's copy button, verify immediately with `cat .env | grep KEY_NAME` (checking for stray quotes/spaces), and ideally test the key directly against the provider's auth endpoint before restarting any service — catches formatting issues before they cost a debug cycle.

**Also recurring during this**: SSH access was lost once due to the dynamic-IP security group issue described above — resolved the same way (update Source to My IP).

## Current state — DEPLOYMENT COMPLETE AND VERIFIED

**Backend fully deployed and live**:
- All 6 containers running: `postgres`, `redis`, `qdrant`, `backend`, `de-api`, `caddy`.
- Caddy holds a valid Let's Encrypt cert for `verifact.duckdns.org` (auto-renews).
- `https://verifact.duckdns.org/health` returns `200 {"status":"ok"}` from outside the network.

**Extension rebuilt and verified against the real backend**:
- `.env.production` and `manifest.json` both point at `https://verifact.duckdns.org`.
- Compiled `extension/content.js` confirmed to contain zero references to `localhost:8000`.

**AI pipeline confirmed working end-to-end**:
- OpenRouter key is valid and has credits.
- `/analyze` runs the full pipeline (translation → query building → fetching → credibility filtering → synthesis) without errors.
- This is the first fully clean pipeline run since the Caddy/HTTPS work began.

**Full stack is live and functional: extension → HTTPS → backend → AI pipeline → real verdicts.**

## Next steps, in order

1. **Manual sanity check in Chrome** (if not already done this session): load the rebuilt extension unpacked (`chrome://extensions` → Developer mode → Load unpacked → `extension/` folder), run a real check on a live webpage, confirm a non-`NOT_SURE` verdict renders and the network tab shows the request going to `verifact.duckdns.org`.

2. **Distribute to testers**: Chrome Web Store (unlisted, $5 one-time + review wait) recommended over manual zip-share, per Ngan's staged rollout plan (tech communities first) — zip-share is a fine stopgap if testing needs to start before store review clears.

## Open items / flags for new session
- Confirm/resolve the `rootkey.csv` question (real root key or not?)
- **Confirm/investigate the second EC2 instance** (`52.220.34.233`) — intentional or orphaned/costing money unnecessarily?
- Consider moving `.pem` + IAM credential CSV out of iCloud sync eventually (not urgent)
- Jenkins: explicitly decided NOT needed at this stage — GitHub Actions is the right future CI/CD path if/when needed
- Domain name: explicitly deferred, using free DuckDNS subdomain instead — revisit only if/when there's a real reason
- Dynamic IP + SSH: if the security-group-source friction keeps recurring, consider AWS Systems Manager Session Manager as a longer-term fix
- Note for future sessions: this Mac's filesystem MCP intermittently returns "File not found" on `edit_file`/`str_replace` calls against files in this iCloud-synced project folder, even immediately after a successful read (likely iCloud sync locking). Reliable workaround: re-read the file, then use `write_file` to overwrite the whole file rather than a partial edit.
