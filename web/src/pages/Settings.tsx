/**
 * Settings — trading mode, Binance keys, AI-provider config and API tokens.
 * Admin only. Switching to Live needs a typed confirmation; the engine also
 * blocks any switch while positions are open.
 */
import { useCallback, useEffect, useState } from "react";

import { I } from "../components/icons";
import {
  Badge,
  Button,
  Card,
  type Column,
  DataTable,
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
  updateAiSettings,
  updateBinanceKeys,
  updateMode,
} from "../lib/api/settings";
import {
  type ApiToken,
  createToken,
  fetchTokens,
  revokeToken,
} from "../lib/api/tokens";

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

const AI_PROVIDERS = ["claude", "openai", "codex", "deepseek", "ollama", "gemini"];

const selectStyle = {
  height: 34,
  padding: "0 10px",
  background: "#18181B",
  border: "1px solid #27272A",
  borderRadius: 8,
  color: "#E4E4E7",
  fontSize: 12.5,
  minWidth: 160,
} as const;

export function Settings() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [tokens, setTokens] = useState<ApiToken[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Trading mode + Binance keys.
  const [pendingLive, setPendingLive] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");

  // AI provider config.
  const [aiProvider, setAiProvider] = useState("claude");
  const [aiModel, setAiModel] = useState("");
  const [aiBaseUrl, setAiBaseUrl] = useState("");
  const [aiKey, setAiKey] = useState("");

  // API tokens.
  const [tokenName, setTokenName] = useState("");
  const [tokenRole, setTokenRole] = useState<"user" | "admin">("user");
  const [newToken, setNewToken] = useState<string | null>(null);

  const applySettings = useCallback((s: SettingsData) => {
    setSettings(s);
    setAiProvider(s.ai_provider);
    setAiModel(s.ai_model);
    setAiBaseUrl(s.ai_base_url);
  }, []);

  const load = useCallback(async () => {
    try {
      const [s, t] = await Promise.all([fetchSettings(), fetchTokens()]);
      applySettings(s);
      setTokens(t);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load settings");
    }
  }, [applySettings]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = useCallback(
    async (fn: () => Promise<void>) => {
      setBusy(true);
      setError(null);
      try {
        await fn();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Action failed");
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const applyMode = (mode: TradingMode, confirm: boolean) =>
    run(async () => {
      applySettings(await updateMode(mode, confirm));
      setNotice(`Trading mode set to ${mode}.`);
    });

  const onPickMode = (mode: TradingMode) => {
    if (!settings || mode === settings.mode) return;
    if (mode === "live") {
      setConfirmText("");
      setPendingLive(true);
    } else {
      void applyMode(mode, false);
    }
  };

  const saveBinanceKeys = () =>
    run(async () => {
      await updateBinanceKeys(apiKey, apiSecret);
      setApiKey("");
      setApiSecret("");
      setNotice("Binance API keys saved.");
      await load();
    });

  const saveAiSettings = () =>
    run(async () => {
      applySettings(await updateAiSettings(aiProvider, aiModel, aiBaseUrl, aiKey));
      setAiKey("");
      setNotice("AI provider settings saved.");
    });

  const createApiToken = () =>
    run(async () => {
      const created = await createToken(tokenName, tokenRole);
      setNewToken(created.token);
      setTokenName("");
      setNotice(null);
      setTokens(await fetchTokens());
    });

  const revoke = (id: number) =>
    run(async () => {
      await revokeToken(id);
      setTokens(await fetchTokens());
    });

  if (!settings) {
    return error ? (
      <EmptyState icon={<I.Warn />} title="Couldn't load settings" body={error} />
    ) : null;
  }

  const tokenCols: Column<ApiToken>[] = [
    { key: "name", label: "Name" },
    { key: "role", label: "Role" },
    {
      key: "created_at",
      label: "Created",
      render: (r) => (
        <span className="num">{(r.created_at ?? "").slice(0, 10)}</span>
      ),
    },
    {
      key: "last_used_at",
      label: "Last used",
      render: (r) => (
        <span className="num">
          {r.last_used_at ? r.last_used_at.slice(0, 19).replace("T", " ") : "—"}
        </span>
      ),
    },
    {
      key: "status",
      label: "Status",
      render: (r) =>
        r.revoked ? (
          <Badge tone="red">Revoked</Badge>
        ) : (
          <Badge tone="green">Active</Badge>
        ),
    },
    {
      key: "actions",
      label: "",
      align: "right",
      render: (r) => (
        <Button
          size="sm"
          kind="outline"
          disabled={r.revoked || busy}
          onClick={() => void revoke(r.id)}
        >
          Revoke
        </Button>
      ),
    },
  ];

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
            onClick={() => void saveBinanceKeys()}
          >
            Save keys
          </Button>
        </div>
      </Card>

      <Card>
        <SectionHeader
          title="AI provider"
          subtitle="Powers AI strategies and the analyze-and-decide endpoint."
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
            <Badge tone={settings.ai_key_configured ? "green" : "muted"}>
              {settings.ai_key_configured ? "API key set" : "No API key"}
            </Badge>
          </div>
          <select
            value={aiProvider}
            onChange={(e) => setAiProvider(e.target.value)}
            style={selectStyle}
          >
            {AI_PROVIDERS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <Input
            full
            placeholder="Model (blank = provider default)"
            value={aiModel}
            onChange={(e) => setAiModel(e.target.value)}
          />
          <Input
            full
            placeholder="Base URL (OpenAI-compatible endpoints)"
            value={aiBaseUrl}
            onChange={(e) => setAiBaseUrl(e.target.value)}
          />
          <Input
            full
            type="password"
            placeholder="API key (blank keeps the current one)"
            value={aiKey}
            onChange={(e) => setAiKey(e.target.value)}
          />
          <Button kind="primary" disabled={busy} onClick={() => void saveAiSettings()}>
            Save AI settings
          </Button>
        </div>
      </Card>

      <Card>
        <SectionHeader
          title="API tokens"
          subtitle="Role-scoped, revocable tokens for agents and the MCP server."
        />
        <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
            <Input
              placeholder="Token name"
              value={tokenName}
              onChange={(e) => setTokenName(e.target.value)}
            />
            <SegmentedControl
              size="sm"
              options={[
                { value: "user", label: "User" },
                { value: "admin", label: "Admin" },
              ]}
              value={tokenRole}
              onChange={setTokenRole}
            />
            <Button
              kind="primary"
              disabled={busy || !tokenName}
              onClick={() => void createApiToken()}
            >
              Create token
            </Button>
          </div>
          {newToken && (
            <div
              style={{
                padding: 10,
                background: "#0E2A1B",
                border: "1px solid #1F5138",
                borderRadius: 8,
                fontSize: 12,
              }}
            >
              <div style={{ color: "var(--text-2)", marginBottom: 4 }}>
                New token — copy it now, it is shown only once:
              </div>
              <code style={{ wordBreak: "break-all", color: "#34D399" }}>{newToken}</code>
            </div>
          )}
          {tokens.length === 0 ? (
            <EmptyState
              icon={<I.Settings />}
              title="No API tokens"
              body="Create a token to let an agent or the MCP server reach the API."
            />
          ) : (
            <DataTable columns={tokenCols} rows={tokens} rowKey={(r) => r.id} dense />
          )}
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
