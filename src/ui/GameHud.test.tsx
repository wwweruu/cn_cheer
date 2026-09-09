import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  Camp,
  GameSettings,
  MoveRecord,
  PieceType,
  Position,
} from "../game/types";
import { GameHud, type GameHudProps } from "./GameHud";
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

  it("prefixes identical pieces that share the origin file", () => {
    expect(
      formatMoveLabel({
        ...move("red", "cannon", { file: 1, rank: 6 }, { file: 1, rank: 5 }),
        disambiguation: "front",
      }),
    ).toBe("前炮进1");
    expect(
      formatMoveLabel({
        ...move("red", "cannon", { file: 1, rank: 7 }, { file: 1, rank: 8 }),
        disambiguation: "back",
      }),
    ).toBe("后炮退1");
    expect(
      formatMoveLabel({
        ...move("black", "soldier", { file: 4, rank: 4 }, { file: 4, rank: 5 }),
        disambiguation: "middle",
      }),
    ).toBe("中卒进1");
  });
});

const baseSettings: GameSettings = {
  quality: "auto",
  effects: "full",
  sound: true,
  cameraShake: true,
};

function renderHud(overrides: Partial<GameHudProps> = {}) {
  const onImportFen = vi.fn<(fen: string) => boolean>().mockReturnValue(true);
  const props: GameHudProps = {
    turn: "red",
    inCheck: false,
    winner: null,
    isDraw: false,
    moves: [],
    fen: "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1",
    canUndo: false,
    settings: baseSettings,
    cameraMode: "perspective",
    onUndo: vi.fn(),
    onRestart: vi.fn(),
    onImportFen,
    onResetCamera: vi.fn(),
    onCameraModeChange: vi.fn(),
    onSettingsChange: vi.fn(),
    ...overrides,
  };
  render(<GameHud {...props} />);
  return { ...props, onImportFen };
}

describe("game record tools", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    });
  });

  afterEach(cleanup);

  it("copies the current FEN and the game record from the settings panel", async () => {
    const moves = [
      move("red", "cannon", { file: 7, rank: 7 }, { file: 4, rank: 7 }),
    ];
    renderHud({ moves });

    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    fireEvent.click(screen.getByRole("button", { name: "复制 FEN" }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "复制棋谱" }));
    await screen.findByRole("button", { name: "已复制" });
    expect(navigator.clipboard.writeText).toHaveBeenLastCalledWith("1. 炮二平五");
  });

  it("disables copying the game record before any move", () => {
    renderHud();
    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    expect(screen.getByRole("button", { name: "复制棋谱" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "复制 FEN" })).toBeEnabled();
  });

  it.each([
    { winner: null, isDraw: true, result: "和棋" },
    { winner: "red" as const, isDraw: false, result: "赤军胜" },
    { winner: "black" as const, isDraw: false, result: "玄军胜" },
  ])("appends $result when copying a finished game", async ({ winner, isDraw, result }) => {
    renderHud({
      winner,
      isDraw,
      moves: [move("red", "cannon", { file: 7, rank: 7 }, { file: 4, rank: 7 })],
    });
    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    fireEvent.click(screen.getByRole("button", { name: "复制棋谱" }));
    await screen.findByRole("button", { name: "已复制" });
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(`1. 炮二平五\n\n${result}`);
  });

  it("imports a FEN through the dialog and reports rejected input", () => {
    const props = renderHud();
    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    fireEvent.click(screen.getByRole("button", { name: "导入 FEN" }));

    const dialog = screen.getByRole("dialog", { name: "导入局面" });
    expect(within(dialog).getByLabelText("FEN 局面串")).toHaveValue(props.fen);

    fireEvent.click(within(dialog).getByRole("button", { name: "载入局面" }));
    expect(props.onImportFen).toHaveBeenCalledWith(props.fen);
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "导入 FEN" }));
    const reopened = screen.getByRole("dialog", { name: "导入局面" });
    props.onImportFen.mockReturnValue(false);
    fireEvent.change(within(reopened).getByLabelText("FEN 局面串"), {
      target: { value: "broken" },
    });
    fireEvent.click(within(reopened).getByRole("button", { name: "载入局面" }));
    expect(screen.getByRole("alert")).toHaveTextContent("FEN 无效");
  });
});
