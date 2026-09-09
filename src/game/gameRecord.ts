import {
  createGameStateFromFen,
  createInitialGameState,
  tryMove,
} from "./rules/xiangqiEngine";
import type { Camp, GameState, MoveRecord, Piece, PieceType } from "./types";

export const GAME_STORAGE_KEY = "xuanjia-xiangqi-game";

const SAVE_VERSION = 2;

const camps: readonly Camp[] = ["red", "black"];
const pieceTypes: readonly PieceType[] = [
  "general",
  "advisor",
  "elephant",
  "horse",
  "chariot",
  "cannon",
  "soldier",
];

export interface SavedGame {
  version: number;
  startFen: string;
  fen: string;
  moves: MoveRecord[];
}

export interface RestoredGame {
  startFen: string;
  game: GameState;
  moves: MoveRecord[];
  history: GameState[];
}

function isIntegerInRange(value: unknown, min: number, max: number): value is number {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= min &&
    value <= max
  );
}

function isPosition(value: unknown): value is { file: number; rank: number } {
  if (typeof value !== "object" || value === null) return false;
  const { file, rank } = value as { file?: unknown; rank?: unknown };
  return isIntegerInRange(file, 0, 8) && isIntegerInRange(rank, 0, 9);
}

function isPiece(value: unknown): value is Piece {
  if (typeof value !== "object" || value === null) return false;
  const piece = value as Partial<Piece>;
  return (
    isIntegerInRange(piece.id, 1, Number.MAX_SAFE_INTEGER) &&
    (piece.camp === "red" || piece.camp === "black") &&
    pieceTypes.includes(piece.type as PieceType) &&
    isPosition(piece.position)
  );
}

function isMoveRecord(value: unknown): value is MoveRecord {
  if (typeof value !== "object" || value === null) return false;
  const move = value as Partial<MoveRecord>;
  return (
    typeof move.id === "number" &&
    isPosition(move.from) &&
    isPosition(move.to) &&
    isPiece(move.piece) &&
    (move.captured === null || isPiece(move.captured)) &&
    typeof move.givesCheck === "boolean" &&
    (move.winner === null || camps.includes(move.winner as Camp))
  );
}

export function saveGame(state: GameState, moves: MoveRecord[], startFen: string): void {
  try {
    localStorage.setItem(
      GAME_STORAGE_KEY,
      JSON.stringify({ version: SAVE_VERSION, startFen, fen: state.fen, moves }),
    );
  } catch {
    // Storage can be unavailable (private mode, quota); keep playing without persistence.
  }
}

export function clearSavedGame(): void {
  try {
    localStorage.removeItem(GAME_STORAGE_KEY);
  } catch {
    // Ignore unavailable storage.
  }
}

export function loadSavedGame(): SavedGame | null {
  try {
    const raw = localStorage.getItem(GAME_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const candidate = parsed as { version?: unknown; startFen?: unknown; fen?: unknown; moves?: unknown };
    if (
      (candidate.version !== SAVE_VERSION && candidate.version !== 1) ||
      (candidate.version === SAVE_VERSION && typeof candidate.startFen !== "string") ||
      typeof candidate.fen !== "string" ||
      !Array.isArray(candidate.moves) ||
      !candidate.moves.every(isMoveRecord)
    ) {
      return null;
    }
    // Version 1 did not store the origin: only standard games and untouched
    // imported positions can be recovered without guessing missing history.
    const startFen = candidate.version === 1
      ? (candidate.moves.length ? createInitialGameState().fen : candidate.fen)
      : candidate.startFen as string;
    return { version: SAVE_VERSION, startFen, fen: candidate.fen, moves: candidate.moves };
  } catch {
    return null;
  }
}

/**
 * Rebuilds a resumable game from a save. Moves are replayed from the saved starting
 * position so undo history and derived flags (check, winner, captures) are
 * recomputed instead of trusted from storage. Any inconsistency discards the
 * save and lets the caller fall back to a fresh game.
 */
export function restoreSavedGame(saved: SavedGame): RestoredGame | null {
  let game: GameState;
  try {
    game = createGameStateFromFen(saved.startFen);
  } catch {
    return null;
  }
  const startFen = game.fen;
  const history: GameState[] = [];
  const moves: MoveRecord[] = [];

  for (const record of saved.moves) {
    const result = tryMove(game, record.from, record.to, record.id);
    if (!result) return null;
    if (
      result.move.piece.camp !== record.piece.camp ||
      result.move.piece.type !== record.piece.type
    ) {
      return null;
    }
    history.push(game);
    moves.push(result.move);
    game = result.state;
  }

  if (game.fen !== saved.fen) return null;
  return { startFen, game, moves, history };
}
