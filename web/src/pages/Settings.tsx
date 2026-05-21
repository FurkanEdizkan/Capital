/**
 * Settings — trading mode (Sim / Testnet / Live) and Binance API keys.
 * Admin only. Switching to Live needs a typed confirmation; the engine also
 * blocks any switch while positions are open.
 */
import { useCallback, useEffect, useState } from "react";

import { I } from "../components/icons";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Modal,
  SectionHeader,
  SegmentedControl,
} from "../components/ui";
import {
  fetchSettings,
  type Settings as SettingsData,
  type TradingMode,
  updateBinanceKeys,
  updateMode,
} from "../lib/api/settings";

const MODES: { value: TradingMode; label: string }[] = [
  { value: "sim", label: "Simulation" },
  { value: "testnet", label: "Testnet" },
  { value: "live", label: "Live" },
];

const MODE_NOTE: Record<TradingMode, string> = {
  sim: "Simulation fills orders on live prices — no real money at risk.",
  testnet: "Testnet places real orders against Binance Testnet funds.",
  live: "⚠ Live mode places real orders with real funds.",
};

export function Settings() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pendingLive, setPendingLive] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setSettings(await fetchSettings());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load settings");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const applyMode = useCallback(async (mode: TradingMode, confirm: boolean) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      setSettings(await updateMode(mode, confirm));
      setNotice(`Trading mode set to ${mode}.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to change mode");
    } finally {
      setBusy(false);
    }
  }, []);

  const onPickMode = (mode: TradingMode) => {
    if (!settings || mode === settings.mode) return;
    if (mode === "live") {
      setConfirmText("");
      setPendingLive(true);
    } else {
      void applyMode(mode, false);
    }
  };

  const saveKeys = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await updateBinanceKeys(apiKey, apiSecret);
      setApiKey("");
      setApiSecret("");
      setNotice("Binance API keys saved.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save keys");
    } finally {
      setBusy(false);
    }
  };

  if (!settings) {
    return error ? (
      <EmptyState icon={<I.Warn />} title="Couldn't load settings" body={error} />
    ) : null;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <Card>
        <SectionHeader
          title="Trading mode"
          subtitle="Sim is paper trading. Testnet and Live place real orders on Binance."
        />
        <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
          <SegmentedControl options={MODES} value={settings.mode} onChange={onPickMode} />
          <span style={{ fontSize: 12, color: "var(--text-2)" }}>
            {MODE_NOTE[settings.mode]}
          </span>
        </div>
      </Card>

      <Card>
        <SectionHeader
          title="Binance API keys"
          subtitle="Stored encrypted at rest. Required for Testnet and Live trading."
        />
        <div
          style={{
            padding: 14,
            display: "flex",
            flexDirection: "column",
            gap: 10,
            maxWidth: 420,
          }}
        >
          <div>
            <Badge tone={settings.binance_keys_configured ? "green" : "muted"}>
              {settings.binance_keys_configured ? "Configured" : "Not set"}
            </Badge>
          </div>
          <Input
            full
            type="password"
            placeholder="API key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
          <Input
            full
            type="password"
            placeholder="API secret"
            value={apiSecret}
            onChange={(e) => setApiSecret(e.target.value)}
          />
          <Button
            kind="primary"
            disabled={busy || !apiKey || !apiSecret}
            onClick={() => void saveKeys()}
          >
            Save keys
          </Button>
        </div>
      </Card>

      {notice && <div style={{ fontSize: 12, color: "#34D399" }}>{notice}</div>}
      {error && <div style={{ fontSize: 12, color: "#F87171" }}>{error}</div>}

      <Modal
        open={pendingLive}
        onClose={() => setPendingLive(false)}
        title="Switch to live trading"
        footer={
          <>
            <Button kind="ghost" onClick={() => setPendingLive(false)}>
              Cancel
            </Button>
            <Button
              kind="danger"
              disabled={confirmText !== "LIVE" || busy}
              onClick={() => {
                setPendingLive(false);
                void applyMode("live", true);
              }}
            >
              Enable live trading
            </Button>
          </>
        }
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <span style={{ fontSize: 13 }}>
            Live mode places <strong>real orders with real funds</strong>. Type{" "}
            <strong>LIVE</strong> to confirm.
          </span>
          <Input
            full
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder="LIVE"
          />
        </div>
      </Modal>
    </div>
  );
}
