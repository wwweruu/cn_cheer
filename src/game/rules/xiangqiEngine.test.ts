import { describe, expect, it } from "vitest";
import { positionKey } from "../coordinates";
import {
  createGameStateFromFen,
  createInitialGameState,
  getLegalMoves,
  getPieceAt,
  tryMove,
} from "./xiangqiEngine";

describe("xiangqi rules adapter", () => {
  it("creates the standard red-to-move position", () => {
    const state = createInitialGameState();
    expect(state.turn).toBe("red");
    expect(state.pieces).toHaveLength(32);
    expect(state.inCheck).toBe(false);
    expect(state.winner).toBeNull();

    const moveCount = state.pieces
      .filter((piece) => piece.camp === "red")
      .reduce((total, piece) => total + getLegalMoves(state, piece.position).length, 0);
    expect(moveCount).toBe(44);
  });

  it("applies horse-leg, pawn-river and cannon-screen rules", () => {
    const state = createInitialGameState();
    const horseMoves = new Set(getLegalMoves(state, { file: 1, rank: 9 }).map(positionKey));
    expect(horseMoves).toEqual(new Set(["0:7", "2:7"]));

    const pawnMoves = new Set(getLegalMoves(state, { file: 0, rank: 6 }).map(positionKey));
    expect(pawnMoves).toEqual(new Set(["0:5"]));

    const cannonMoves = new Set(getLegalMoves(state, { file: 1, rank: 7 }).map(positionKey));
    expect(cannonMoves.has("1:0")).toBe(true);
    expect(cannonMoves.has("1:2")).toBe(false);
  });

  it("blocks a horse at its leg and an elephant at its eye", () => {
    const horseState = createGameStateFromFen(
      "4k4/9/9/9/4P4/4N4/9/9/9/4K4 w - - 0 1",
    );
    const horseMoves = new Set(
      getLegalMoves(horseState, { file: 4, rank: 5 }).map(positionKey),
    );
    expect(horseMoves.has("3:3")).toBe(false);
    expect(horseMoves.has("5:3")).toBe(false);
    expect(horseMoves.has("2:4")).toBe(true);

    const elephantState = createGameStateFromFen(
      "4k4/9/9/9/4P4/9/9/9/1R7/2B1K4 w - - 0 1",
    );
    const elephantMoves = new Set(
      getLegalMoves(elephantState, { file: 2, rank: 9 }).map(positionKey),
    );
    expect(elephantMoves.has("0:7")).toBe(false);
    expect(elephantMoves.has("4:7")).toBe(true);
  });

  it("keeps advisors and generals inside the palace", () => {
    const state = createInitialGameState();
    expect(getLegalMoves(state, { file: 3, rank: 9 })).toEqual([
      { file: 4, rank: 8 },
    ]);
    expect(getLegalMoves(state, { file: 4, rank: 9 })).toEqual([
      { file: 4, rank: 8 },
    ]);
  });

  it("rejects a move that exposes facing generals", () => {
    const state = createGameStateFromFen("4k4/9/9/9/4P4/9/9/9/9/4K4 w - - 0 1");
    const moves = new Set(getLegalMoves(state, { file: 4, rank: 4 }).map(positionKey));
    expect(moves.has("3:4")).toBe(false);
    expect(moves.has("4:3")).toBe(true);
  });

  it("only offers moves that resolve an active check", () => {
    const state = createGameStateFromFen(
      "4k4/9/9/9/4r4/9/9/9/9/4K4 w - - 0 1",
    );
    expect(state.inCheck).toBe(true);
    expect(
      new Set(getLegalMoves(state, { file: 4, rank: 9 }).map(positionKey)),
    ).toEqual(new Set(["3:9", "5:9"]));
  });

  it("preserves piece identity and changes turn after a legal move", () => {
    const state = createInitialGameState();
    const before = getPieceAt(state, { file: 0, rank: 6 });
    const result = tryMove(state, { file: 0, rank: 6 }, { file: 0, rank: 5 }, 1);

    expect(result).not.toBeNull();
    expect(result?.state.turn).toBe("black");
    expect(result?.move.piece.id).toBe(before?.id);
    expect(getPieceAt(result!.state, { file: 0, rank: 5 })?.id).toBe(before?.id);
    expect(getPieceAt(result!.state, { file: 0, rank: 6 })).toBeNull();
  });

  it("reports a known checkmate position", () => {
    const state = createGameStateFromFen(
      "1nbakabn1/r7r/1c7/p1p1C1p1p/4C2c1/9/P1P1P1P1P/9/9/RNBAKABNR b - - 4 4",
    );
    expect(state.inCheck).toBe(true);
    expect(state.winner).toBe("red");
  });

  it("reports a stalemate as a win without check", () => {
    const state = createGameStateFromFen(
      "4k4/3R1R3/9/9/9/4P4/9/9/9/4K4 b - - 0 1",
    );
    expect(state.inCheck).toBe(false);
    expect(state.winner).toBe("red");
  });
});
