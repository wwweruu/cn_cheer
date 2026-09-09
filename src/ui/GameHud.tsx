import { useState } from "react";
import {
  ArrowCounterClockwise,
  ArrowClockwise,
  Camera,
  Check,
  GearSix,
  SpeakerHigh,
  SpeakerSlash,
  Sparkle,
  SquaresFour,
  Sword,
  Waveform,
  X,
} from "@phosphor-icons/react";
import type {
  CameraMode,
  Camp,
  GameSettings,
  MoveRecord,
} from "../game/types";
import { copyToClipboard } from "./clipboard";
import { formatMoveLabel } from "./moveNotation";

function PlayerRow({ camp, active, inCheck }: { camp: Camp; active: boolean; inCheck: boolean }) {
  const red = camp === "red";
  return (
    <div className={`player-row player-row--${camp}${active ? " is-active" : ""}`}>
      <div className="player-seal" aria-hidden="true">
        {red ? "帅" : "将"}
      </div>
      <div className="player-copy">
        <strong>{red ? "赤军" : "玄军"}</strong>
        <span>{active ? (inCheck ? "应将" : "行棋") : "候阵"}</span>
      </div>
      {active && <span className="turn-marker">当前</span>}
    </div>
  );
}

function formatGameRecord(moves: MoveRecord[], winner: Camp | null, isDraw: boolean): string {
  const lines = moves.map((move, index) => `${index + 1}. ${formatMoveLabel(move)}`);
  if (winner) lines.push("", winner === "red" ? "赤军胜" : "玄军胜");
  else if (isDraw) lines.push("", "和棋");
  return lines.join("\n");
}

export interface GameHudProps {
  turn: Camp;
  inCheck: boolean;
  winner: Camp | null;
  isDraw: boolean;
  moves: MoveRecord[];
  fen: string;
  canUndo: boolean;
  settings: GameSettings;
  cameraMode: CameraMode;
  onUndo: () => void;
  onRestart: () => void;
  onImportFen: (fen: string) => boolean;
  onResetCamera: () => void;
  onCameraModeChange: (mode: CameraMode) => void;
  onSettingsChange: (settings: Partial<GameSettings>) => void;
}

export function GameHud({
  turn,
  inCheck,
  winner,
  isDraw,
  moves,
  fen,
  canUndo,
  settings,
  cameraMode,
  onUndo,
  onRestart,
  onImportFen,
  onResetCamera,
  onCameraModeChange,
  onSettingsChange,
}: GameHudProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [confirmRestart, setConfirmRestart] = useState(false);
  const [fenDialogOpen, setFenDialogOpen] = useState(false);
  const [fenDraft, setFenDraft] = useState("");
  const [fenError, setFenError] = useState<string | null>(null);
  const [copiedLabel, setCopiedLabel] = useState<string | null>(null);
  const capturedRed = moves.filter((move) => move.captured?.camp === "red").length;
  const capturedBlack = moves.filter((move) => move.captured?.camp === "black").length;

  const copyGameText = async (label: string, text: string) => {
    if (await copyToClipboard(text)) {
      setCopiedLabel(label);
      window.setTimeout(() => setCopiedLabel(null), 1600);
    }
  };

  const openFenDialog = () => {
    setFenDraft(fen);
    setFenError(null);
    setFenDialogOpen(true);
  };

  const submitFen = () => {
    if (onImportFen(fenDraft)) {
      setFenDialogOpen(false);
      return;
    }
    setFenError("FEN 无效或局面不合法，请检查后重试。");
  };

  return (
    <aside className="game-hud" aria-label="对局信息与控制">
      <header className="hud-header">
        <div>
          <p>玄甲棋局</p>
          <h1>{winner ? `${winner === "red" ? "赤军" : "玄军"}胜` : isDraw ? "和棋" : inCheck ? "将军" : "阵中对弈"}</h1>
        </div>
        <button
          className={`icon-button${settingsOpen ? " is-active" : ""}`}
          type="button"
          aria-label={settingsOpen ? "关闭设置" : "打开设置"}
          title={settingsOpen ? "关闭设置" : "设置"}
          onClick={() => setSettingsOpen((value) => !value)}
        >
          {settingsOpen ? <X size={19} /> : <GearSix size={20} />}
        </button>
      </header>

      <section className="player-stack" aria-label="双方状态">
        <PlayerRow camp="black" active={!winner && !isDraw && turn === "black"} inCheck={inCheck} />
        <div className="battle-count" aria-label="已损失棋子">
          <span>玄军折损 {capturedBlack}</span>
          <Sword size={17} aria-hidden="true" />
          <span>赤军折损 {capturedRed}</span>
        </div>
        <PlayerRow camp="red" active={!winner && !isDraw && turn === "red"} inCheck={inCheck} />
      </section>

      <div className="tool-row" aria-label="棋局操作">
        <button
          className="icon-button"
          type="button"
          aria-label="悔棋"
          title="悔棋"
          disabled={!canUndo}
          onClick={onUndo}
        >
          <ArrowCounterClockwise size={20} />
        </button>
        <button
          className="icon-button"
          type="button"
          aria-label="重新开局"
          title="重新开局"
          onClick={() => (moves.length ? setConfirmRestart(true) : onRestart())}
        >
          <ArrowClockwise size={20} />
        </button>
        <button
          className="icon-button"
          type="button"
          aria-label="复位镜头"
          title="复位镜头"
          onClick={onResetCamera}
        >
          <Camera size={20} />
        </button>
        <button
          className="icon-button"
          type="button"
          aria-label={cameraMode === "top" ? "切换斜视" : "切换顶视"}
          title={cameraMode === "top" ? "斜视" : "顶视"}
          onClick={() => onCameraModeChange(cameraMode === "top" ? "perspective" : "top")}
        >
          <SquaresFour size={20} weight={cameraMode === "top" ? "fill" : "regular"} />
        </button>
        <button
          className={`icon-button${settings.sound ? " is-active" : ""}`}
          type="button"
          role="switch"
          aria-checked={settings.sound}
          aria-label={settings.sound ? "关闭音效" : "开启音效"}
          title={settings.sound ? "关闭音效" : "开启音效"}
          onClick={() => onSettingsChange({ sound: !settings.sound })}
        >
          {settings.sound ? <SpeakerHigh size={20} /> : <SpeakerSlash size={20} />}
        </button>
        <button
          className={`icon-button${settings.effects !== "off" ? " is-active" : ""}`}
          type="button"
          aria-label={`特效：${settings.effects === "full" ? "完整" : settings.effects === "reduced" ? "简洁" : "关闭"}`}
          title="切换特效"
          onClick={() =>
            onSettingsChange({
              effects:
                settings.effects === "full"
                  ? "reduced"
                  : settings.effects === "reduced"
                    ? "off"
                    : "full",
            })
          }
        >
          <Sparkle size={20} weight={settings.effects === "full" ? "fill" : "regular"} />
        </button>
        <button
          className={`icon-button camera-shake-tool${settings.cameraShake ? " is-active" : ""}`}
          type="button"
          role="switch"
          aria-checked={settings.cameraShake}
          aria-label={settings.cameraShake ? "关闭镜头震动" : "开启镜头震动"}
          title={settings.cameraShake ? "关闭镜头震动" : "开启镜头震动"}
          onClick={() => onSettingsChange({ cameraShake: !settings.cameraShake })}
        >
          <Waveform size={20} weight={settings.cameraShake ? "bold" : "regular"} />
        </button>
      </div>

      {settingsOpen ? (
        <section className="settings-panel" aria-label="表现设置">
          <div className="setting-heading">
            <Sparkle size={19} aria-hidden="true" />
            <h2>表现设置</h2>
          </div>
          <fieldset>
            <legend>画面质量</legend>
            <div className="segmented-control">
              {([["auto", "自动"], ["high", "精细"], ["low", "流畅"]] as const).map(([value, label]) => (
                <button key={value} type="button" className={settings.quality === value ? "is-selected" : ""}
                  aria-pressed={settings.quality === value} onClick={() => onSettingsChange({ quality: value })}>{label}</button>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend>特效强度</legend>
            <div className="segmented-control">
              {([
                ["full", "完整"],
                ["reduced", "简洁"],
                ["off", "关闭"],
              ] as const).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={settings.effects === value ? "is-selected" : ""}
                  onClick={() => onSettingsChange({ effects: value })}
                >
                  {settings.effects === value && <Check size={14} weight="bold" />}
                  {label}
                </button>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend>棋局</legend>
            <div className="record-actions">
              <button
                type="button"
                className="button-secondary"
                onClick={() => copyGameText("FEN", fen)}
              >
                {copiedLabel === "FEN" ? "已复制" : "复制 FEN"}
              </button>
              <button type="button" className="button-secondary" onClick={openFenDialog}>
                导入 FEN
              </button>
              <button
                type="button"
                className="button-secondary"
                disabled={moves.length === 0}
                onClick={() => copyGameText("棋谱", formatGameRecord(moves, winner, isDraw))}
              >
                {copiedLabel === "棋谱" ? "已复制" : "复制棋谱"}
              </button>
            </div>
          </fieldset>
          <button
            className="switch-row"
            type="button"
            role="switch"
            aria-checked={settings.cameraShake}
            onClick={() => onSettingsChange({ cameraShake: !settings.cameraShake })}
          >
            <span>镜头震动</span>
            <span className={`switch${settings.cameraShake ? " is-on" : ""}`} aria-hidden="true">
              <span />
            </span>
          </button>
        </section>
      ) : (
        <section className="move-history" aria-label="着法记录">
          <div className="history-heading">
            <h2>着法</h2>
            <span>{moves.length} 手</span>
          </div>
          {moves.length === 0 ? (
            <div className="empty-history">
              <span className="empty-seal">局</span>
              <p>静候首着</p>
            </div>
          ) : (
            <ol>
              {[...moves]
                .reverse()
                .slice(0, 8)
                .map((move) => (
                  <li key={move.id}>
                    <span>{String(move.id).padStart(2, "0")}</span>
                    <strong>{formatMoveLabel(move)}</strong>
                    <small>
                      {move.captured ? "吃子" : move.givesCheck ? "将军" : move.piece.camp === "red" ? "赤" : "玄"}
                    </small>
                  </li>
                ))}
            </ol>
          )}
        </section>
      )}

      <footer className="hud-footer">
        <span>本地双人</span>
        <span>{cameraMode === "top" ? "顶视" : "斜视"}</span>
      </footer>

      {fenDialogOpen && (
        <div className="dialog-backdrop" role="presentation" onMouseDown={() => setFenDialogOpen(false)}>
          <section
            className="confirm-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="fen-import-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <h2 id="fen-import-title">导入局面</h2>
            <p>粘贴 FEN 局面串，从该局面继续对弈。导入后着法记录与悔棋历史将清空。</p>
            <textarea
              className="fen-input"
              value={fenDraft}
              rows={3}
              aria-label="FEN 局面串"
              onChange={(event) => {
                setFenDraft(event.target.value);
                setFenError(null);
              }}
            />
            {fenError && (
              <p className="fen-error" role="alert">
                {fenError}
              </p>
            )}
            <div>
              <button type="button" className="button-secondary" onClick={() => setFenDialogOpen(false)}>
                取消
              </button>
              <button type="button" className="button-primary" onClick={submitFen}>
                载入局面
              </button>
            </div>
          </section>
        </div>
      )}

      {confirmRestart && (
        <div className="dialog-backdrop" role="presentation" onMouseDown={() => setConfirmRestart(false)}>
          <section
            className="confirm-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="restart-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <h2 id="restart-title">重新布阵？</h2>
            <p>当前棋局与着法记录将被清空。</p>
            <div>
              <button type="button" className="button-secondary" onClick={() => setConfirmRestart(false)}>
                取消
              </button>
              <button
                type="button"
                className="button-primary"
                onClick={() => {
                  setConfirmRestart(false);
                  onRestart();
                }}
              >
                重新开局
              </button>
            </div>
          </section>
        </div>
      )}
    </aside>
  );
}
