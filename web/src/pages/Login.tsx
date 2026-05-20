/**
 * Login screen — ported from the design bundle (screens/login.jsx).
 * Phase 0: authenticates against the mock auth context (no engine yet).
 */
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { BrandMark, I } from "../components/icons";
import { Button, Input } from "../components/ui";
import { useAuth } from "../lib/auth";

export function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("ada");
  const [password, setPassword] = useState("demo-password");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = (e?: FormEvent) => {
    if (e) e.preventDefault();
    setBusy(true);
    // Mock latency, then sign in. Real auth posts to the engine in a later phase.
    setTimeout(() => {
      setBusy(false);
      signIn(username);
      navigate("/", { replace: true });
    }, 500);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "radial-gradient(circle at 50% 0%, #16161A 0%, var(--bg) 60%)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
          maskImage: "radial-gradient(ellipse at center, #000 30%, transparent 75%)",
          WebkitMaskImage: "radial-gradient(ellipse at center, #000 30%, transparent 75%)",
          pointerEvents: "none",
        }}
      />

      <div style={{ position: "relative", width: 380, maxWidth: "100%" }}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            marginBottom: 24,
          }}
        >
          <BrandMark size={42} />
          <div style={{ marginTop: 12, fontSize: 20, fontWeight: 700, letterSpacing: "-.01em" }}>
            Capital
          </div>
          <div
            style={{
              fontSize: 12.5,
              color: "var(--text-3)",
              marginTop: 2,
              fontFamily: "var(--mono)",
            }}
          >
            self-hosted trading engine
          </div>
        </div>

        <form
          onSubmit={submit}
          style={{
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: 12,
            padding: 22,
            boxShadow: "0 30px 60px rgba(0,0,0,.4), 0 1px 0 rgba(255,255,255,.02) inset",
          }}
        >
          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Sign in</div>
            <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 4 }}>
              Operator credentials are required to access the engine console.
            </div>
          </div>

          <label
            style={{
              display: "block",
              fontSize: 11.5,
              color: "var(--text-2)",
              marginBottom: 6,
              fontWeight: 500,
            }}
          >
            Username
          </label>
          <Input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            full
            placeholder="username"
          />

          <div style={{ height: 14 }} />

          <label
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: 11.5,
              color: "var(--text-2)",
              marginBottom: 6,
              fontWeight: 500,
            }}
          >
            <span>Password</span>
            <a style={{ color: "var(--text-3)", cursor: "pointer" }}>Forgot?</a>
          </label>
          <Input
            type={show ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            full
            placeholder="••••••••••••"
            suffix={
              <button
                type="button"
                onClick={() => setShow((s) => !s)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--text-3)",
                  cursor: "pointer",
                  padding: 0,
                  display: "inline-flex",
                }}
              >
                {show ? <I.EyeOff /> : <I.Eye />}
              </button>
            }
          />

          <div
            style={{
              marginTop: 14,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <label
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 7,
                fontSize: 12,
                color: "var(--text-2)",
                cursor: "pointer",
              }}
            >
              <input type="checkbox" defaultChecked style={{ accentColor: "#10B981" }} />
              Trust this device for 14 days
            </label>
          </div>

          <div style={{ height: 18 }} />
          <Button kind="primary" size="lg" full type="submit" disabled={busy}>
            {busy ? "Authenticating…" : "Sign in to Capital"}
          </Button>

          <div
            style={{
              marginTop: 18,
              paddingTop: 14,
              borderTop: "1px dashed var(--border-soft)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: 11.5,
              color: "var(--text-3)",
            }}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span
                style={{ width: 6, height: 6, borderRadius: 999, background: "var(--text-4)" }}
              />
              Engine not connected
            </span>
            <span style={{ fontFamily: "var(--mono)" }}>capital.local · v0.1.0</span>
          </div>
        </form>

        <div
          style={{
            marginTop: 18,
            textAlign: "center",
            fontSize: 11.5,
            color: "var(--text-4)",
            fontFamily: "var(--mono)",
          }}
        >
          single-tenant build · audit log enabled
        </div>
      </div>
    </div>
  );
}
