import { beforeEach, describe, expect, it } from "vitest";
import {
  GAME_STORAGE_KEY,
  clearSavedGame,
  loadSavedGame,
  restoreSavedGame,
  saveGame,
} from "./gameRecord";
import { createInitialGameState, tryMove } from "./rules/xiangqiEngine";
import type { GameState, MoveRecord } from "./types";

function playOpening(count: number): { state: GameState; moves: MoveRecord[] } {
  const opening: ReadonlyArray<readonly [{ file: number; rank: number }, { file: number; rank: number }]> = [
    [{ file: 7, rank: 7 }, { file: 4, rank: 7 }], // 炮二平五
    [{ file: 4, rank: 3 }, { file: 4, rank: 4 }], // 卒五进1
    [{ file: 4, rank: 6 }, { file: 4, rank: 5 }], // 兵五进1
  ];
  let state = createInitialGameState();
  const moves: MoveRecord[] = [];
  for (let index = 0; index < count; index += 1) {
    const [from, to] = opening[index];
    const result = tryMove(state, from, to, index + 1);
    if (!result) throw new Error(`opening move ${index + 1} is not legal`);
    moves.push(result.move);
    state = result.state;
  }
  return { state, moves };
}

describe("game record persistence", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("round-trips a played game and rebuilds the undo history", () => {
    const { state, moves } = playOpening(2);
    saveGame(state, moves);

    const saved = loadSavedGame();
    expect(saved).not.toBeNull();
    expect(saved?.fen).toBe(state.fen);
    expect(saved?.moves).toHaveLength(2);

    const restored = restoreSavedGame(saved!);
    expect(restored).not.toBeNull();
    expect(restored?.game.fen).toBe(state.fen);
    expect(restored?.game.turn).toBe("red");
    expect(restored?.moves).toHaveLength(2);
    expect(restored?.history).toHaveLength(2);
    expect(restored?.moves[0].captured).toBeNull();
  });

  it("restores an imported position that was saved without moves", () => {
    const { state } = playOpening(1);
    saveGame(state, []);

    const restored = restoreSavedGame(loadSavedGame()!);
    expect(restored).not.toBeNull();
    expect(restored?.game.fen).toBe(state.fen);
    expect(restored?.moves).toEqual([]);
    expect(restored?.history).toEqual([]);
  });

  it("ignores missing, corrupted or unsupported records", () => {
    expect(loadSavedGame()).toBeNull();

    localStorage.setItem(GAME_STORAGE_KEY, "{not json");
    expect(loadSavedGame()).toBeNull();

    localStorage.setItem(
      GAME_STORAGE_KEY,
      JSON.stringify({ version: 999, fen: "whatever", moves: [] }),
    );
    expect(loadSavedGame()).toBeNull();

    const { state, moves } = playOpening(1);
    saveGame(state, moves);
    const raw = JSON.parse(localStorage.getItem(GAME_STORAGE_KEY)!) as { moves: MoveRecord[] };
    raw.moves[0].from = { file: 9, rank: 7 }; // off-board square fails the shape check
    localStorage.setItem(GAME_STORAGE_KEY, JSON.stringify(raw));
    expect(loadSavedGame()).toBeNull();
  });

  it("rejects records whose moves do not replay legally", () => {
    const { state, moves } = playOpening(1);
    saveGame(state, moves);
    const raw = JSON.parse(localStorage.getItem(GAME_STORAGE_KEY)!) as { moves: MoveRecord[] };
    // Cannon teleporting sideways from its origin square is illegal.
    raw.moves[0].to = { file: 5, rank: 4 };
    localStorage.setItem(GAME_STORAGE_KEY, JSON.stringify(raw));

    const saved = loadSavedGame();
    expect(saved).not.toBeNull();
    expect(restoreSavedGame(saved!)).toBeNull();
  });

  it("rejects records whose stored fen disagrees with the replayed moves", () => {
    const { state, moves } = playOpening(2);
    saveGame(state, moves);
    const raw = JSON.parse(localStorage.getItem(GAME_STORAGE_KEY)!) as { fen: string };
    raw.fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1";
    localStorage.setItem(GAME_STORAGE_KEY, JSON.stringify(raw));

    expect(restoreSavedGame(loadSavedGame()!)).toBeNull();
  });

  it("clears the stored record", () => {
    const { state, moves } = playOpening(1);
    saveGame(state, moves);
    expect(loadSavedGame()).not.toBeNull();

    clearSavedGame();
    expect(loadSavedGame()).toBeNull();
  });
});
