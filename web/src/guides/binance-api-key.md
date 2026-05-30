# Getting a Binance API key

Capital trades through your own Binance account using an API key. The key never
leaves your machine except to talk to Binance, and it is stored **encrypted** in
the database.

## Steps

1. Sign in at [binance.com](https://www.binance.com) and open
   **Account → API Management**.
2. Click **Create API**, choose **System generated**, and label it `capital`.
3. Complete 2FA. Copy the **API Key** and **Secret Key** — the secret is shown
   only once.
4. Under **Edit restrictions**:
   - Enable **Enable Reading** and **Enable Spot & Margin Trading**.
   - Enable **Enable Futures** only if you intend to trade perpetuals.
   - **Do not** enable withdrawals.
   - Optionally restrict to your server's IP address.
5. In Capital, open **Settings → Binance** and paste both values, then save.

## Region blocked?

If Binance is blocked from your location, run Capital behind a VPN or deploy it
on a VPS in a supported region — see the **Deployment** guide.

> Start in **Sim** mode. Only switch to Testnet or Live once you trust the
> behaviour.
