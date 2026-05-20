/**
 * WebSocket message contract.
 *
 * Every message the engine pushes shares one envelope shape with a
 * discriminated `type` field, so the client can switch on `type` with full
 * type-safety. Feature phases add their message types to the `WsMessage`
 * union (market ticks, position updates, engine events, …).
 */

export interface WsEnvelope<TType extends string, TPayload> {
  /** Discriminator — narrows the payload type. */
  type: TType;
  /** ISO-8601 UTC timestamp. */
  ts: string;
  payload: TPayload;
}

/** Engine liveness heartbeat — the first WS message type. */
export type HeartbeatMessage = WsEnvelope<"heartbeat", { uptimeSeconds: number }>;

/**
 * Union of every server→client WebSocket message. Extended as features land:
 *   export type WsMessage = HeartbeatMessage | PriceTickMessage | ...
 */
export type WsMessage = HeartbeatMessage;

/** Type guard for narrowing a parsed message by its `type`. */
export function isWsMessage<T extends WsMessage["type"]>(
  msg: WsMessage,
  type: T,
): msg is Extract<WsMessage, { type: T }> {
  return msg.type === type;
}
