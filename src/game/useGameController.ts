import { useCallback, useMemo, useState } from "react";
import { playMoveSound } from "../audio/sfx";
import { positionKey, samePosition } from "./coordinates";
import {
  createInitialGameState,
  getLegalMoves,
  getPieceAt,
  tryMove,
} from "./rules/xiangqiEngine";
import type {
  CameraMode,
  GameSettings,
  GameState,
  MoveRecord,
  Position,
} from "./types";

const SETTINGS_KEY = "xuanjia-xiangqi-settings";

const defaultSettings: GameSettings = {
  effects: "full",
  sound: true,
  cameraShake: true,
};

function loadSettings(): GameSettings {
  try {
    return {
      ...defaultSettings,
      ...JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? "{}"),
    };
  } catch {
    return defaultSettings;
  }
}

export function useGameController() {
  const [game, setGame] = useState(createInitialGameState);
  const [selected, setSelected] = useState<Position | null>(null);
  const [legalMoves, setLegalMoves] = useState<Position[]>([]);
  const [history, setHistory] = useState<GameState[]>([]);
  const [moves, setMoves] = useState<MoveRecord[]>([]);
  const [animation, setAnimation] = useState<MoveRecord | null>(null);
  const [settings, setSettingsState] = useState<GameSettings>(loadSettings);
  const [cameraMode, setCameraMode] = useState<CameraMode>("perspective");
  const [cameraReset, setCameraReset] = useState(0);

  const legalMoveKeys = useMemo(
    () => new Set(legalMoves.map(positionKey)),
    [legalMoves],
  );

  const select = useCallback(
    (position: Position) => {
      const piece = getPieceAt(game, position);
      if (!piece || piece.camp !== game.turn) return;
      setSelected(position);
      setLegalMoves(getLegalMoves(game, position));
    },
    [game],
  );

  const clickPosition = useCallback(
    (position: Position) => {
      if (animation || game.winner) return;
      const clickedPiece = getPieceAt(game, position);

      if (!selected) {
        select(position);
        return;
      }

      if (samePosition(selected, position)) {
        setSelected(null);
        setLegalMoves([]);
        return;
      }

      if (clickedPiece?.camp === game.turn) {
        select(position);
        return;
      }

      if (!legalMoveKeys.has(positionKey(position))) {
        setSelected(null);
        setLegalMoves([]);
        return;
      }

      const result = tryMove(game, selected, position, moves.length + 1);
      if (!result) return;
      setHistory((current) => [...current, game]);
      setMoves((current) => [...current, result.move]);
      setGame(result.state);
      setAnimation(result.move);
      setSelected(null);
      setLegalMoves([]);
      if (settings.sound) playMoveSound(Boolean(result.move.captured));
    },
    [animation, game, legalMoveKeys, moves.length, select, selected, settings.sound],
  );

  const finishAnimation = useCallback(() => setAnimation(null), []);

  const undo = useCallback(() => {
    if (animation || history.length === 0) return;
    const previous = history.at(-1);
    if (!previous) return;
    setGame(previous);
    setHistory((current) => current.slice(0, -1));
    setMoves((current) => current.slice(0, -1));
    setSelected(null);
    setLegalMoves([]);
  }, [animation, history]);

  const restart = useCallback(() => {
    setGame(createInitialGameState());
    setHistory([]);
    setMoves([]);
    setSelected(null);
    setLegalMoves([]);
    setAnimation(null);
  }, []);

  const updateSettings = useCallback((next: Partial<GameSettings>) => {
    setSettingsState((current) => {
      const value = { ...current, ...next };
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(value));
      return value;
    });
  }, []);

  return {
    game,
    selected,
    legalMoves,
    moves,
    animation,
    settings,
    cameraMode,
    cameraReset,
    canUndo: history.length > 0 && !animation,
    clickPosition,
    finishAnimation,
    undo,
    restart,
    updateSettings,
    setCameraMode,
    resetCamera: () => setCameraReset((value) => value + 1),
  };
}
