/**
 * Feature-screen routes. Each is a stub until its plan phase delivers it
 * (see ScreenStub). Implemented screens replace their stub here.
 */
import { I } from "../components/icons";
import { ScreenStub } from "./ScreenStub";

export function Backtest() {
  return (
    <ScreenStub
      title="Backtest"
      phase="Phase 4"
      icon={<I.Backtest size={22} />}
      summary="Replay a strategy over historical data with a realistic slippage & fee model; view the equity curve and metrics."
    />
  );
}

export function History() {
  return (
    <ScreenStub
      title="History"
      phase="Phase 6"
      icon={<I.History size={22} />}
      summary="The full transaction log, order log, engine events and config audit trail — with CSV/Excel export."
    />
  );
}

export function Settings() {
  return (
    <ScreenStub
      title="Settings"
      phase="Phase 5"
      icon={<I.Settings size={22} />}
      summary="Binance API keys, risk limits, the Sim/Testnet/Live mode toggle, AI provider config and API tokens."
    />
  );
}

export function Users() {
  return (
    <ScreenStub
      title="Users"
      phase="Phase 0"
      icon={<I.Users size={22} />}
      summary="Operator management — create and disable users, assign admin/user roles and reset passwords."
    />
  );
}
