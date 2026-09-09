import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { playMoveSound } from "../audio/sfx";
import { positionKey, samePosition } from "./coordinates";
import {
  clearSavedGame,
  loadSavedGame,
  restoreSavedGame,
  saveGame,
} from "./gameRecord";
import {
  createGameStateFromFen,
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
  MovePlayback,
  Position,
} from "./types";

const SETTINGS_KEY = "xuanjia-xiangqi-settings";

const defaultSettings: GameSettings = {
  quality: "auto",
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

interface BootGame {
  startFen: string;
  game: GameState;
  moves: MoveRecord[];
  history: GameState[];
}

function bootstrapGame(): BootGame {
  const saved = loadSavedGame();
  if (saved) {
    const restored = restoreSavedGame(saved);
    if (restored) return restored;
    clearSavedGame();
  }
  const game = createInitialGameState();
  return { startFen: game.fen, game, moves: [], history: [] };
}

export function useGameController() {
  const [boot] = useState(bootstrapGame);
  const [startFen, setStartFen] = useState(boot.startFen);
  const [game, setGame] = useState<GameState>(boot.game);
  const [selected, setSelected] = useState<Position | null>(null);
  const [legalMoves, setLegalMoves] = useState<Position[]>([]);
  const [history, setHistory] = useState<GameState[]>(boot.history);
  const [moves, setMoves] = useState<MoveRecord[]>(boot.moves);
  const [animation, setAnimation] = useState<MovePlayback | null>(null);
  const playbackSequence = useRef(0);
  const sounded = useRef(0);
  const [settings, setSettingsState] = useState<GameSettings>(loadSettings);
  const [cameraMode, setCameraMode] = useState<CameraMode>("perspective");
  const [cameraReset, setCameraReset] = useState(0);

  const legalMoveKeys = useMemo(
    () => new Set(legalMoves.map(positionKey)),
    [legalMoves],
  );

  const initialFen = useMemo(() => createInitialGameState().fen, []);

  // Persist the committed game so a refresh can resume it. A pristine board
  // (fresh start or every move undone) clears the save instead.
  useEffect(() => {
    if (moves.length > 0 || game.fen !== initialFen) saveGame(game, moves, startFen);
    else clearSavedGame();
  }, [game, moves, initialFen, startFen]);

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
      if (animation || game.winner || game.isDraw) return;
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
      setAnimation({...result.move,token:++playbackSequence.current,startedAt:performance.now(),effectLevel:settings.effects});
      setSelected(null);
      setLegalMoves([]);
    },
    [animation, game, legalMoveKeys, moves.length, select, selected, settings.effects],
  );

  const finishAnimation = useCallback((token:number) => setAnimation(current=>current?.token===token?null:current), []);
  const contactAnimation = useCallback((token:number,captured:boolean) => {
    if(token!==playbackSequence.current||sounded.current===token)return;
    sounded.current=token;if(settings.sound)playMoveSound(captured);
  },[settings.sound]);

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
    ++playbackSequence.current;
    const next = createInitialGameState();
    setGame(next);
    setStartFen(next.fen);
    setHistory([]);
    setMoves([]);
    setSelected(null);
    setLegalMoves([]);
    setAnimation(null);
  }, []);

  const importFen = useCallback((fen: string): boolean => {
    const trimmed = fen.trim();
    if (!trimmed) return false;
    let next: GameState;
    try {
      next = createGameStateFromFen(trimmed);
    } catch {
      return false;
    }
    ++playbackSequence.current;
    setGame(next);
    setStartFen(next.fen);
    setHistory([]);
    setMoves([]);
    setSelected(null);
    setLegalMoves([]);
    setAnimation(null);
    return true;
  }, []);

  const updateSettings = useCallback((next: Partial<GameSettings>) => {
    setSettingsState((current) => {
      const value = { ...current, ...next };
      try {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(value));
      } catch {
        // Keep settings usable for this session when browser storage is unavailable.
      }
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
    contactAnimation,
    undo,
    restart,
    importFen,
    updateSettings,
    setCameraMode,
    resetCamera: () => setCameraReset((value) => value + 1),
  };
}
