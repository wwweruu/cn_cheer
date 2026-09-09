export type Camp = "red" | "black";

export type PieceType =
  | "general"
  | "advisor"
  | "elephant"
  | "horse"
  | "chariot"
  | "cannon"
  | "soldier";

export interface Position {
  file: number;
  rank: number;
}

export interface Piece {
  id: number;
  camp: Camp;
  type: PieceType;
  position: Position;
}

export interface GameState {
  fen: string;
  pieces: Piece[];
  turn: Camp;
  inCheck: boolean;
  winner: Camp | null;
}

/** Position of an identical piece sharing the origin file (前/中/后 disambiguation). */
export type MoveDisambiguation = "front" | "middle" | "back";

export interface MoveRecord {
  id: number;
  from: Position;
  to: Position;
  piece: Piece;
  captured: Piece | null;
  givesCheck: boolean;
  winner: Camp | null;
  /** Set when identical pieces of the same camp share the origin file (e.g. 前炮进二). */
  disambiguation?: MoveDisambiguation;
}

/** Monotonic playback identity survives undo/restart and LOD changes. */
export interface MovePlayback extends MoveRecord {
  token: number;
  startedAt: number;
  effectLevel: EffectLevel;
}

export interface MoveResult {
  state: GameState;
  move: MoveRecord;
}

export type EffectLevel = "full" | "reduced" | "off";
export type CameraMode = "perspective" | "top";
export type ModelQuality = "auto" | "high" | "low";

export interface GameSettings {
  quality: ModelQuality;
  effects: EffectLevel;
  sound: boolean;
  cameraShake: boolean;
}
