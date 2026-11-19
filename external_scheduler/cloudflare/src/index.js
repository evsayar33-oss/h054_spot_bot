/** Independent UTC clock for Regime Band-30 PAPER.
 * GitHub PAT is stored ONLY as a Cloudflare Worker secret.
 * No trade or ledger access; triggers an existing idempotent workflow.
 */
const OWNER = "evsayar33-oss";
const REPO = "h054_spot_bot";
const EVENT = "regime-band30-external-tick";

export default {
  async scheduled(controller, env) {
    if (!env.GITHUB_DISPATCH_TOKEN) throw new Error("MISSING_GITHUB_DISPATCH_TOKEN");
    const response = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/dispatches`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.GITHUB_DISPATCH_TOKEN}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "regime-band30-independent-clock"
      },
      body: JSON.stringify({event_type: EVENT, client_payload: {scheduled_time: controller.scheduledTime}})
    });
    if (response.status !== 204) {
      // Never log token, request headers, or GitHub response body.
      throw new Error(`GITHUB_DISPATCH_FAILED_HTTP_${response.status}`);
    }
    console.log("REGIME_EXTERNAL_DISPATCH_ACCEPTED");
  },
  async fetch() {
    return new Response("Independent scheduler: active only via cron", {status: 200});
  }
};
