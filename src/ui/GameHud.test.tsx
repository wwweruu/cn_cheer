import { describe, expect, it } from "vitest";
import type { Camp, MoveRecord, PieceType, Position } from "../game/types";
import { formatMoveLabel } from "./moveNotation";

function move(
  camp: Camp,
  type: PieceType,
  from: Position,
  to: Position,
): MoveRecord {
  return {
    id: 1,
    from,
    to,
    piece: { id: 1, camp, type, position: from },
    captured: null,
    givesCheck: false,
    winner: null,
  };
}

describe("Chinese move notation", () => {
  it("uses each camp's forward direction", () => {
    expect(
      formatMoveLabel(move("red", "soldier", { file: 4, rank: 6 }, { file: 4, rank: 5 })),
    ).toBe("兵五进1");
    expect(
      formatMoveLabel(move("black", "soldier", { file: 4, rank: 3 }, { file: 4, rank: 4 })),
    ).toBe("卒五进1");
    expect(
      formatMoveLabel(move("black", "soldier", { file: 4, rank: 4 }, { file: 4, rank: 3 })),
    ).toBe("卒五退1");
  });

  it("uses the destination file for diagonal pieces", () => {
    expect(
      formatMoveLabel(move("red", "horse", { file: 1, rank: 9 }, { file: 2, rank: 7 })),
    ).toBe("马八进七");
    expect(
      formatMoveLabel(move("black", "advisor", { file: 3, rank: 0 }, { file: 4, rank: 1 })),
    ).toBe("士四进五");
  });
});
