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

export interface MoveRecord {
  id: number;
  from: Position;
  to: Position;
  piece: Piece;
  captured: Piece | null;
  givesCheck: boolean;
  winner: Camp | null;
}

export interface MoveResult {
  state: GameState;
  move: MoveRecord;
}

export type EffectLevel = "full" | "reduced" | "off";
export type CameraMode = "perspective" | "top";

export interface GameSettings {
  effects: EffectLevel;
  sound: boolean;
  cameraShake: boolean;
}
