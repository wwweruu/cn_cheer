import { Component, type ErrorInfo, type ReactNode } from "react";
import { GameScene } from "./scene/GameScene";
import { GameHud } from "./ui/GameHud";
import { useGameController } from "./game/useGameController";
import { AssetLoadingStatus } from "./ui/AssetLoadingStatus";

class SceneErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("3D scene failed", error, info);
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="scene-error" role="alert">
          <strong>3D 棋盘启动失败</strong>
          <span>请确认浏览器已开启 WebGL 硬件加速。</span>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const controller = useGameController();

  return (
    <main className="game-app">
      <section className="scene-stage" aria-label="玄甲棋局 3D 棋盘" data-testid="scene-stage">
        <div className="scene-brand" aria-hidden="true">
          <span>玄</span>
          <div>
            <strong>玄甲棋局</strong>
            <small>赤军先行</small>
          </div>
        </div>
        {controller.game.inCheck && !controller.game.winner && !controller.game.isDraw && (
          <div className="check-banner" role="status">
            将军
          </div>
        )}
        <SceneErrorBoundary>
          <GameScene
            pieces={controller.game.pieces}
            selected={controller.selected}
            legalMoves={controller.legalMoves}
            moves={controller.moves}
            animation={controller.animation}
            effects={controller.settings.effects}
            quality={controller.settings.quality}
            cameraShake={controller.settings.cameraShake}
            cameraMode={controller.cameraMode}
            cameraReset={controller.cameraReset}
            onPositionClick={controller.clickPosition}
            onMoveComplete={controller.finishAnimation}
            onContact={controller.contactAnimation}
          />
        </SceneErrorBoundary>
        <AssetLoadingStatus />
        {(controller.game.winner || controller.game.isDraw) && (
          <div className="victory-band" role="status">
            <span>{controller.game.isDraw ? "双方和局" : controller.game.winner === "red" ? "赤军" : "玄军"}</span>
            <strong>{controller.game.isDraw ? "和棋" : "破阵"}</strong>
            <button type="button" onClick={controller.restart}>
              再开一局
            </button>
          </div>
        )}
      </section>
      <GameHud
        turn={controller.game.turn}
        inCheck={controller.game.inCheck}
        winner={controller.game.winner}
        isDraw={controller.game.isDraw}
        moves={controller.moves}
        fen={controller.game.fen}
        canUndo={controller.canUndo}
        settings={controller.settings}
        cameraMode={controller.cameraMode}
        onUndo={controller.undo}
        onRestart={controller.restart}
        onImportFen={controller.importFen}
        onResetCamera={controller.resetCamera}
        onCameraModeChange={controller.setCameraMode}
        onSettingsChange={controller.updateSettings}
      />
    </main>
  );
}
