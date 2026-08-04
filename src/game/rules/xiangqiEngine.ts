import { makeFen, parseFen } from "elephantops/fen";
import type {
  Color as EngineColor,
  Piece as EnginePiece,
  Role as EngineRole,
  Square,
} from "elephantops/types";
import {
  squareFile,
  squareFromCoords,
  squareRank,
} from "elephantops/util";
import { Xiangqi } from "elephantops/xiangqi";
import { samePosition } from "../coordinates";
import type {
  GameState,
  MoveResult,
  Piece,
  PieceType,
  Position,
} from "../types";

const engineRoleToPiece: Record<EngineRole, PieceType> = {
  king: "general",
  advisor: "advisor",
  elephant: "elephant",
  horse: "horse",
  chariot: "chariot",
  cannon: "cannon",
  pawn: "soldier",
};

function toEngineSquare(position: Position): Square {
  const square = squareFromCoords(position.file, 9 - position.rank);
  if (square === undefined) throw new Error("棋盘坐标超出范围");
  return square;
}

function fromEngineSquare(square: Square): Position {
  return { file: squareFile(square), rank: 9 - squareRank(square) };
}

function createPosition(fen: string): Xiangqi {
  return Xiangqi.fromSetup(parseFen(fen).unwrap()).unwrap();
}

function readInitialPieces(position: Xiangqi): Piece[] {
  return [...position.board]
    .sort(([left], [right]) => left - right)
    .map(([square, piece], index) => ({
      id: index + 1,
      camp: piece.color,
      type: engineRoleToPiece[piece.role],
      position: fromEngineSquare(square),
    }));
}

function hydrateGameState(position: Xiangqi, pieces: Piece[]): GameState {
  return {
    fen: makeFen(position.toSetup()),
    pieces,
    turn: position.turn,
    inCheck: position.isCheck(),
    winner: position.outcome()?.winner ?? null,
  };
}

export function createInitialGameState(): GameState {
  const position = Xiangqi.default();
  return hydrateGameState(position, readInitialPieces(position));
}

export function createGameStateFromFen(fen: string): GameState {
  const position = createPosition(fen);
  return hydrateGameState(position, readInitialPieces(position));
}

export function getPieceAt(state: GameState, position: Position): Piece | null {
  return state.pieces.find((piece) => samePosition(piece.position, position)) ?? null;
}

export function getLegalMoves(state: GameState, from: Position): Position[] {
  const piece = getPieceAt(state, from);
  if (!piece || piece.camp !== state.turn || state.winner) return [];
  const position = createPosition(state.fen);
  return [...position.dests(toEngineSquare(from))].map(fromEngineSquare);
}

export function tryMove(
  state: GameState,
  from: Position,
  to: Position,
  moveId: number,
): MoveResult | null {
  const movingPiece = getPieceAt(state, from);
  if (!movingPiece || movingPiece.camp !== state.turn || state.winner) return null;

  const engine = createPosition(state.fen);
  const move = { from: toEngineSquare(from), to: toEngineSquare(to) };
  if (!engine.isLegal(move)) return null;

  const captured = getPieceAt(state, to);
  engine.play(move);
  const pieces = state.pieces
    .filter((piece) => piece.id !== captured?.id)
    .map((piece) =>
      piece.id === movingPiece.id ? { ...piece, position: { ...to } } : piece,
    );
  const nextState = hydrateGameState(engine, pieces);
  return {
    state: nextState,
    move: {
      id: moveId,
      from,
      to,
      piece: movingPiece,
      captured,
      givesCheck: nextState.inCheck,
      winner: nextState.winner,
    },
  };
}

export function enginePieceAt(state: GameState, position: Position): EnginePiece | undefined {
  return createPosition(state.fen).board.get(toEngineSquare(position));
}

export function engineTurn(state: GameState): EngineColor {
  return createPosition(state.fen).turn;
}
