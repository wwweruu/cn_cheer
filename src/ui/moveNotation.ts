import type { MoveDisambiguation, MoveRecord, PieceType } from "../game/types";

const pieceLabels: Record<PieceType, { red: string; black: string }> = {
  general: { red: "帅", black: "将" },
  advisor: { red: "仕", black: "士" },
  elephant: { red: "相", black: "象" },
  horse: { red: "马", black: "马" },
  chariot: { red: "车", black: "车" },
  cannon: { red: "炮", black: "炮" },
  soldier: { red: "兵", black: "卒" },
};

const disambiguationLabels: Record<MoveDisambiguation, string> = {
  front: "前",
  middle: "中",
  back: "后",
};

const fileNames = ["一", "二", "三", "四", "五", "六", "七", "八", "九"];

export function formatMoveLabel(move: MoveRecord) {
  const piece = pieceLabels[move.piece.type][move.piece.camp];
  const toFile = move.piece.camp === "red" ? 8 - move.to.file : move.to.file;
  const advances =
    move.piece.camp === "red"
      ? move.to.rank < move.from.rank
      : move.to.rank > move.from.rank;
  const action = move.from.rank === move.to.rank ? "平" : advances ? "进" : "退";
  const usesTargetFile =
    action === "平" ||
    move.piece.type === "horse" ||
    move.piece.type === "elephant" ||
    move.piece.type === "advisor";
  const target = usesTargetFile
    ? fileNames[toFile]
    : String(Math.abs(move.to.rank - move.from.rank));

  if (move.disambiguation) {
    return `${disambiguationLabels[move.disambiguation]}${piece}${action}${target}`;
  }

  const fromFile = move.piece.camp === "red" ? 8 - move.from.file : move.from.file;
  return `${piece}${fileNames[fromFile]}${action}${target}`;
}
