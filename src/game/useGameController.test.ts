import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getPieceAt } from "./rules/xiangqiEngine";
import { useGameController } from "./useGameController";
import { playMoveSound } from '../audio/sfx';

vi.mock("../audio/sfx", () => ({ playMoveSound: vi.fn() }));

describe("game controller", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it.each(["QuotaExceededError", "SecurityError"])(
    "keeps settings usable when storage throws %s",
    (errorName) => {
      const { result } = renderHook(() => useGameController());
      vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
        throw new DOMException("Storage unavailable", errorName);
      });

      act(() => result.current.updateSettings({ sound: false }));
      expect(result.current.settings.sound).toBe(false);

      act(() => result.current.updateSettings({ quality: "low" }));
      expect(result.current.settings).toEqual({
        sound: false,
        quality: "low",
        effects: "full",
        cameraShake: true,
      });
      act(() => result.current.clickPosition({ file: 4, rank: 6 }));
      expect(result.current.selected).toEqual({ file: 4, rank: 6 });
    },
  );

  it("persists settings for the next controller", () => {
    const { result, unmount } = renderHook(() => useGameController());
    act(() => result.current.updateSettings({ sound: false, quality: "low" }));
    const settings = result.current.settings;
    unmount();

    const restored = renderHook(() => useGameController());
    expect(restored.result.current.settings).toEqual(settings);
  });

  it("locks input during animation and restores a move with undo", () => {
    const { result } = renderHook(() => useGameController());

    act(() => result.current.clickPosition({ file: 4, rank: 6 }));
    expect(result.current.selected).toEqual({ file: 4, rank: 6 });
    expect(result.current.legalMoves).toContainEqual({ file: 4, rank: 5 });

    act(() => result.current.clickPosition({ file: 4, rank: 5 }));
    expect(result.current.game.turn).toBe("black");
    expect(result.current.moves).toHaveLength(1);
    expect(result.current.animation).not.toBeNull();
    expect(result.current.canUndo).toBe(false);

    act(() => result.current.clickPosition({ file: 0, rank: 3 }));
    expect(result.current.moves).toHaveLength(1);

    act(() => result.current.finishAnimation(result.current.animation!.token));
    expect(result.current.canUndo).toBe(true);

    act(() => result.current.undo());
    expect(result.current.game.turn).toBe("red");
    expect(result.current.moves).toHaveLength(0);
    expect(getPieceAt(result.current.game, { file: 4, rank: 6 })).not.toBeNull();
    expect(getPieceAt(result.current.game, { file: 4, rank: 5 })).toBeNull();
  });

  it("clears committed and animated state when restarting", () => {
    const { result } = renderHook(() => useGameController());

    act(() => result.current.clickPosition({ file: 4, rank: 6 }));
    act(() => result.current.clickPosition({ file: 4, rank: 5 }));
    expect(result.current.moves).toHaveLength(1);

    act(() => result.current.restart());
    expect(result.current.game.turn).toBe("red");
    expect(result.current.game.pieces).toHaveLength(32);
    expect(result.current.moves).toHaveLength(0);
    expect(result.current.animation).toBeNull();
    expect(result.current.selected).toBeNull();
  });

  it('ignores stale animation callbacks after restart and plays contact once',()=>{
    const {result}=renderHook(()=>useGameController());
    const move=()=>{act(()=>result.current.clickPosition({file:4,rank:6}));act(()=>result.current.clickPosition({file:4,rank:5}));};
    move();const old=result.current.animation!.token;
    expect(playMoveSound).not.toHaveBeenCalled();
    act(()=>result.current.restart());move();const current=result.current.animation!.token;
    expect(current).toBeGreaterThan(old);
    act(()=>{result.current.finishAnimation(old);result.current.contactAnimation(old,false);});
    expect(result.current.animation?.token).toBe(current);expect(playMoveSound).not.toHaveBeenCalled();
    act(()=>{result.current.contactAnimation(current,false);result.current.contactAnimation(current,false);});
    expect(playMoveSound).toHaveBeenCalledTimes(1);
    act(()=>result.current.finishAnimation(current));expect(result.current.animation).toBeNull();
  });
});
