import { describe, expect, it } from "vitest";
import {
  boardToWorld,
  positionToSquareId,
  squareIdToPosition,
} from "./coordinates";

describe("board coordinates", () => {
  it("round trips every board intersection", () => {
    for (let rank = 0; rank < 10; rank += 1) {
      for (let file = 0; file < 9; file += 1) {
        const position = { file, rank };
        expect(squareIdToPosition(positionToSquareId(position))).toEqual(position);
      }
    }
  });

  it("centers the board symmetrically in world space", () => {
    const northWest = boardToWorld({ file: 0, rank: 0 });
    const southEast = boardToWorld({ file: 8, rank: 9 });
    expect(northWest[0]).toBe(-southEast[0]);
    expect(northWest[2]).toBe(-southEast[2]);
    expect(northWest[1]).toBe(0);
  });
});
