import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import * as rules from "./game/rules/xiangqiEngine";
import type { GameScene } from "./scene/GameScene";

// Exercise the real controller and HUD without requiring a WebGL renderer.
vi.mock("./scene/GameScene", () => ({
  GameScene: ({ onPositionClick, onMoveComplete, animation }: ComponentProps<typeof GameScene>) => (
    <div>
      <button onClick={() => onPositionClick({ file: 4, rank: 9 })}>选择红帅</button>
      <button onClick={() => onPositionClick({ file: 4, rank: 8 })}>吃掉最后一卒</button>
      <button onClick={() => onPositionClick({ file: 3, rank: 0 })}>选择黑将</button>
      <button onClick={() => onPositionClick({ file: 3, rank: 1 })}>移动黑将</button>
      {animation && <button onClick={() => onMoveComplete(animation.token)}>完成动画</button>}
    </div>
  ),
}));
vi.mock("./ui/AssetLoadingStatus", () => ({ AssetLoadingStatus: () => null }));

describe("drawn game", () => {
  beforeEach(() => {
    localStorage.clear();
    const state = rules.createGameStateFromFen("3k5/9/9/9/9/9/9/9/4p4/4K4 w - - 0 1");
    vi.spyOn(rules, "createInitialGameState").mockReturnValueOnce(state);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  function finishDraw() {
    fireEvent.click(screen.getByRole("button", { name: "选择红帅" }));
    fireEvent.click(screen.getByRole("button", { name: "吃掉最后一卒" }));
    fireEvent.click(screen.getByRole("button", { name: "完成动画" }));
  }

  it("shows the draw, stops further moves and allows undo to resume play", () => {
    render(<App />);
    finishDraw();

    expect(screen.getByRole("heading", { name: "和棋" })).toBeInTheDocument();
    expect(within(screen.getByRole("status")).getByText("和棋")).toBeInTheDocument();
    expect(screen.queryByText("当前")).not.toBeInTheDocument();
    expect(screen.getByText("1 手")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "选择黑将" }));
    fireEvent.click(screen.getByRole("button", { name: "移动黑将" }));
    expect(screen.getByText("1 手")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "完成动画" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "悔棋" }));
    expect(screen.queryByRole("heading", { name: "和棋" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "再开一局" })).not.toBeInTheDocument();
    expect(screen.getByText("当前")).toBeInTheDocument();
    expect(screen.getByText("0 手")).toBeInTheDocument();
    finishDraw();
    expect(screen.getByRole("heading", { name: "和棋" })).toBeInTheDocument();
  });

  it("starts a fresh game from the draw result", () => {
    render(<App />);
    finishDraw();
    fireEvent.click(screen.getByRole("button", { name: "再开一局" }));

    expect(screen.getByRole("heading", { name: "阵中对弈" })).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByText("0 手")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "悔棋" })).toBeDisabled();
  });
});
