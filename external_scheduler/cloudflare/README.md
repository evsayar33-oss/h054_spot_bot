# Regime Band-30 independent scheduler (Cloudflare Workers)

This clock runs outside GitHub Actions scheduling. It sends a GitHub `repository_dispatch` event to the existing Regime Band-30 PAPER workflow; it never accesses or rewrites the PAPER ledger. GitHub Actions still executes the observation, so GitHub Actions service outages or runner delays remain possible. The scheduler reduces dependence on GitHub's **cron** service, not on GitHub Actions itself.

## One-time setup (requires your own Cloudflare account)

1. Merge this PR to `main`. In GitHub, create a **fine-grained personal access token** restricted to repository `evsayar33-oss/h054_spot_bot`, with **Contents: Read and write** (GitHub repository dispatch endpoint permission). Set an expiration and rotate it periodically. Never commit or paste the token in a PR/chat.
2. Install Node.js and run `cd external_scheduler/cloudflare && npm install` (or `npx wrangler` directly).
3. Authenticate: `npx wrangler login`.
4. Store the token privately: `npx wrangler secret put GITHUB_DISPATCH_TOKEN`. Paste the token only into the CLI secret prompt.
5. Deploy: `npx wrangler deploy`.
6. Check Cloudflare Workers > Triggers for `10,30,50 * * * *` UTC. Inspect Worker logs for `REGIME_EXTERNAL_DISPATCH_ACCEPTED` and GitHub Actions runs triggered by `repository_dispatch` (event type `regime-band30-external-tick`). A 204 means GitHub accepted dispatch, **not** that the PAPER job succeeded; verify its jobs and ledger.

## Safety and operation

- Existing GitHub cron, workflow_run and manual dispatch remain available; the workflow concurrency group serializes runs and `tick()` deduplicates already processed candles.
- Do not run `start` to repair missed observations; no historical order-book quotes or trades are synthesized.
- Cloudflare free-tier limits and cron scheduling are subject to provider terms; monitor dispatch failures and GitHub Actions runs.
- To disable only this external clock, remove the Worker cron trigger or delete the Worker. GitHub triggers continue independently.
- No repository Secrets are required for this Worker. Its PAT resides only in Cloudflare Worker Secrets. A leaked PAT must be revoked immediately.
