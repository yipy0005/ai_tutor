# Cloudflare Tunnel deployment

This guide publishes the single-household Flask app through a dedicated Cloudflare hostname. The recommended shape is:

```text
browser -- HTTPS + Cloudflare Access --> named Tunnel --> http://127.0.0.1:5001
```

The Tunnel is transport, not authorization. Put a restrictive Cloudflare Access policy on the hostname before exposing learner or parent data. The app still performs its own learner login, parent PIN, CSRF, and ownership checks.

> These steps summarize Cloudflare's current official workflow. Verify dashboard labels and connector commands against [Cloudflare's Tunnel getting-started guide](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/) and [self-hosted Access guide](https://developers.cloudflare.com/cloudflare-one/applications/configure-apps/self-hosted-apps/).

## Deployment boundary

This repository is designed for one household on one persistent machine. The normal launcher uses Flask's built-in server and SQLite. A Tunnel with Access is suitable for a tightly restricted family deployment, not a multi-family production service. For a larger service, add a production WSGI process, database, backup plan, login throttling, and monitoring before publishing it.

Use a dedicated hostname such as `tutor.example.com`, not a path below another application. The app generates root-relative links and assets.

## 1. Prepare the origin

1. Complete the one-time parent setup locally on `http://127.0.0.1:5001` before publishing the hostname. Direct loopback setup does not need a token; it consumes the setup capability when the first learner is created. If setup must happen through the public hostname, configure Cloudflare Access first and use the token-gated path described below.
2. Make sure `instance/tutor.sqlite3`, its backups, and the generated `instance/secret_key` live on durable storage. Do not copy `instance/` into the repository or serve it as static content.
3. Install `cloudflared` on the same Mac as the app. Cloudflare's current macOS install path is documented in [Downloads](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/):

   ```bash
   brew install cloudflared
   ```

4. Start the origin on loopback only:

   ```bash
   pixi run cloudflare-origin
   ```

   This sets `HOST=127.0.0.1`, `PORT=5001`, and `SESSION_COOKIE_SECURE=1`. The browser-facing Cloudflare URL is HTTPS; the Tunnel's local hop remains HTTP. Do not use the normal `pixi run serve` binding of `0.0.0.0` for this setup, and do not port-forward port 5001.

If this is a new database and setup must happen through the public hostname, configure Cloudflare Access first, set `PARENT_SETUP_REQUIRE_TOKEN=1`, and set `PARENT_BOOTSTRAP_TOKEN` through a secret manager before the first app start. Never place the token in this file, the Tunnel config, a URL, or a normal log. The normal `pixi run cloudflare-origin` task already enables the forced token gate; local loopback setup is the tokenless alternative.

For an existing database already marked as set up, `PARENT_BOOTSTRAP_TOKEN` is not needed for normal startup.

## 2. Create a named Tunnel

Cloudflare recommends a remotely managed Tunnel for most new deployments. The dashboard stores the route configuration, while the connector runs on this Mac.

1. Add the domain to Cloudflare and open **Networking → Tunnels** in the Cloudflare dashboard.
2. Select **Create a tunnel**, name it, choose the Mac operating system, and run the connector installation command shown by Cloudflare on the origin machine. Do not commit that command, its token, or generated credential files.
3. After the connector is healthy, add a **Published application** route:
   - Hostname: `tutor.example.com`
   - Service URL: `http://127.0.0.1:5001`
4. Confirm the Tunnel reports **Healthy** before testing the application.

Cloudflare's current dashboard flow is described in [Create a tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-remote-tunnel/). A Tunnel is outbound from the origin, so no router port-forward or inbound firewall rule for port 5001 is needed.

### Optional locally managed configuration

Cloudflare recommends remotely managed tunnels, but the repository includes a non-secret example for local management at [`cloudflared/config.example.yml`](../cloudflared/config.example.yml). Copy it to the local `cloudflared` directory only after replacing the placeholders, and keep the generated JSON credential file outside the repository.

The locally managed workflow is documented by Cloudflare in [Locally managed tunnels](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/configure-tunnels/local-management/) and [Configuration file](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/configure-tunnels/local-management/configuration-file/). The final ingress rule must remain the catch-all `http_status:404` rule.

## 3. Add Cloudflare Access before testing

Create a self-hosted Access application for the exact public hostname:

1. Go to **Zero Trust → Access controls → Applications**.
2. Choose **Create new application → Self-hosted and private**.
3. Add the public hostname `tutor.example.com`.
4. Add an **Allow** policy for only the parent/operator email identities that should reach this household app. Do not use an Everyone policy.
5. Enable only the identity providers the household needs.
6. Test the Access policy in a private browser window before sharing the URL.

The safest family deployment protects the whole hostname. That means each child device must complete the Access challenge before it reaches the learner login. If children cannot use Access, protecting only `/parent/*` leaves the learner application publicly reachable; that is a weaker deployment and should not be treated as equivalent privacy protection.

Cloudflare Access is an outer gate. Do not add code that trusts `Cf-Access-*` identity headers as parent authentication. The Flask app must continue to use its own accounts and sessions.

## 4. Runtime secrets and cookies

Set these through the host's secret manager or process environment, not in a committed file:

- `SECRET_KEY`: persistent, high-entropy value. Changing it logs out every browser session.
- `SESSION_COOKIE_SECURE=1`: required for the public HTTPS hostname.
- `PARENT_SETUP_REQUIRE_TOKEN=1`: force the bootstrap-token gate even for a loopback origin; required by the included Cloudflare origin task.
- `PARENT_BOOTSTRAP_TOKEN`: only while an unconfigured database needs first-run setup; at least 32 characters.
- `DATABASE_URL`: normally leave unset so the app uses the persistent `instance/tutor.sqlite3` SQLite file for this household deployment.

Never expose `instance/`, SQLite files, backups, `secret_key`, token files, or Tunnel credential JSON through the hostname. Do not enable Flask debug mode.

## 5. Verify the deployment

From a device outside the home network, verify in this order:

1. The hostname presents HTTPS and Cloudflare Access blocks an unapproved identity.
2. An approved identity reaches the app and receives the learner/parent login flow.
3. Learner A cannot access learner B's account, quests, or progress.
4. Parent access still requires the app's parent PIN and remains scoped to linked learners.
5. CSRF-protected form and API actions work through the hostname.
6. A restart of both Flask and `cloudflared` preserves the database, secret key, and sessions as expected.
7. Backups can be taken and restored with the app stopped.

Keep the Flask process and Tunnel connector supervised by the host OS if the URL must remain available. Do not run multiple app workers against this SQLite file without deliberate concurrency testing.

## Useful troubleshooting

- **502 / connection refused:** confirm `pixi run cloudflare-origin` is running and that `http://127.0.0.1:5001` responds locally.
- **Login loops:** check that `SESSION_COOKIE_SECURE=1` is set for the HTTPS hostname and that `SECRET_KEY` is stable across restarts.
- **Tunnel healthy but hostname is denied:** inspect the Access application hostname and Allow policy before changing the Flask app.
- **Public first-run setup appears:** stop publishing, complete setup locally, or configure Access and `PARENT_BOOTSTRAP_TOKEN` before starting a new database.
- **Unexpected direct LAN access:** confirm the origin is bound to `127.0.0.1`, not `0.0.0.0`.
