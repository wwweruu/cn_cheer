import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getPieceAt } from "./rules/xiangqiEngine";
import { useGameController } from "./useGameController";
import { playMoveSound } from '../audio/sfx';

vi.mock("../audio/sfx", () => ({ playMoveSound: vi.fn() }));

describe("game controller", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
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
