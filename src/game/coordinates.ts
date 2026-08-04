import type { Position } from "./types";

export const BOARD_SPACING = 1.05;

export function positionToSquareId({ file, rank }: Position): string {
  return `${String.fromCharCode(97 + file)}${10 - rank}`;
}

export function squareIdToPosition(squareId: string): Position {
  return {
    file: squareId.charCodeAt(0) - 97,
    rank: 10 - Number(squareId.slice(1)),
  };
}

export function positionKey({ file, rank }: Position): string {
  return `${file}:${rank}`;
}

export function samePosition(a: Position, b: Position): boolean {
  return a.file === b.file && a.rank === b.rank;
}

export function boardToWorld({ file, rank }: Position): [number, number, number] {
  return [(file - 4) * BOARD_SPACING, 0, (rank - 4.5) * BOARD_SPACING];
}
