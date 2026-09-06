import { Suspense, useEffect, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { Group, PCFShadowMap, Vector3 } from "three";
import type {
  CameraMode,
  EffectLevel,
  ModelQuality,
  MoveRecord,
  MovePlayback,
  Piece,
  Position,
} from "../game/types";
import { ArmoredPiece } from "./ArmoredPiece";
import { BattleEffects } from "./BattleEffects";
import { BattlefieldBoard } from "./BattlefieldBoard";
import { initializeAssetLoader } from "../assets/runtimeAssets";
import { Atmosphere } from "./Atmosphere";
import { SceneDiagnostics } from "./SceneDiagnostics";
import { PieceNameplates } from "./PieceNameplates";
import { CAPTURE, playbackDuration, playbackSeconds } from './moveTimeline';

interface GameSceneProps {
  pieces: Piece[];
  selected: Position | null;
  legalMoves: Position[];
  moves: MoveRecord[];
  animation: MovePlayback | null;
  effects: EffectLevel;
  quality: ModelQuality;
  cameraShake: boolean;
  cameraMode: CameraMode;
  cameraReset: number;
  onPositionClick: (position: Position) => void;
  onMoveComplete: (token:number) => void;
  onContact: (token:number,captured:boolean) => void;
}

function CameraRig({ mode, reset }: { mode: CameraMode; reset: number }) {
  const { camera, size } = useThree();
  const controls = useRef<OrbitControlsImpl>(null);
  const desiredPosition = useRef(new Vector3(8.4, 11.2, 14.3));
  const desiredTarget = useRef(new Vector3(0, 0.45, 0));
  const transitioning = useRef(true);

  useEffect(() => {
    const portrait = size.width / size.height < 0.85;
    const landscapeDistanceScale = !portrait && size.height <= 760 ? 1.27 : 1.17;
    desiredPosition.current.set(
      mode === "top" ? 0 : portrait ? 0.01 : 8.4 * landscapeDistanceScale,
      mode === "top"
        ? (portrait ? 28 : 20.5 * landscapeDistanceScale)
        : portrait
          ? 23
          : 0.45 + (11.2 - 0.45) * landscapeDistanceScale,
      mode === "top" ? (portrait ? .65 : .43 * landscapeDistanceScale) : portrait ? 10 : 14.3 * landscapeDistanceScale,
    );
    desiredTarget.current.set(0, mode === "top" ? 0 : 0.45, 0);
    transitioning.current = true;
  }, [mode, reset, size.height, size.width]);

  useFrame(() => {
    if (!controls.current || !transitioning.current) return;
    camera.position.lerp(desiredPosition.current, 0.095);
    controls.current.target.lerp(desiredTarget.current, 0.095);
    controls.current.update();
    if (
      camera.position.distanceTo(desiredPosition.current) < 0.025 &&
      controls.current.target.distanceTo(desiredTarget.current) < 0.02
    ) {
      camera.position.copy(desiredPosition.current);
      controls.current.target.copy(desiredTarget.current);
      controls.current.update();
      transitioning.current = false;
    }
  });

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping
      dampingFactor={0.07}
      minDistance={7.5}
      maxDistance={36}
      minPolarAngle={0.02}
      maxPolarAngle={1.34}
      minAzimuthAngle={-1.2}
      maxAzimuthAngle={1.2}
      target={[0, 0.45, 0]}
      onStart={() => {
        transitioning.current = false;
      }}
    />
  );
}

function Battlefield({
  pieces,
  selected,
  legalMoves,
  moves,
  animation,
  effects,
  quality,
  cameraShake,
  onPositionClick,
  onMoveComplete,
  onContact,
}: Omit<GameSceneProps, "cameraMode" | "cameraReset">) {
  const root = useRef<Group>(null);
  const contactSent = useRef(0);
  const completionSent = useRef(0);
  const visiblePieces = animation?.captured
    ? [...pieces, animation.captured]
    : pieces;

  useFrame(() => {
    if (!root.current) return;
    const t=animation?playbackSeconds(animation):0;
    const contact=animation?.effectLevel==='off'?.04:animation?.captured?CAPTURE.contact:.56;
    if(animation){
      if(t>=contact&&contactSent.current!==animation.token){contactSent.current=animation.token;onContact(animation.token,Boolean(animation.captured));}
      if(t>=playbackDuration(animation)&&completionSent.current!==animation.token){completionSent.current=animation.token;onMoveComplete(animation.token);}
    }
    if (!cameraShake || !animation?.captured || effects !== "full") {
      root.current.position.set(0, 0, 0);
      return;
    }
    const elapsed = t-contact;
    const strength = elapsed<0?0:Math.max(0, 1 - elapsed / 0.35) * 0.025;
    root.current.position.set(
      Math.sin(elapsed * 78) * strength,
      Math.sin(elapsed * 54) * strength * 0.4,
      Math.cos(elapsed * 66) * strength,
    );
  });

  return (
    <group ref={root}>
      <BattlefieldBoard
        selected={selected}
        legalMoves={legalMoves}
        lastMove={moves.at(-1) ?? null}
        onPositionClick={onPositionClick}
      />
      {visiblePieces.map((piece) => (
        <ArmoredPiece
          key={piece.id}
          piece={piece}
          selected={selected?.file === piece.position.file && selected.rank === piece.position.rank}
          move={animation}
          effects={effects}
          quality={quality}
          onClick={() => onPositionClick(piece.position)}
        />
      ))}
      <BattleEffects move={animation} level={effects} />
      <PieceNameplates pieces={visiblePieces}/>
    </group>
  );
}

export function GameScene(props: GameSceneProps) {
  return (
    <Canvas
      className="game-canvas"
      camera={{ position: [8.4, 11.2, 14.3], fov: 39, near: 0.1, far: 70 }}
      dpr={[1, 1.5]}
      shadows={{ type: PCFShadowMap }}
      gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
      onCreated={({ gl }) => initializeAssetLoader(gl)}
      fallback={<div className="canvas-fallback">当前设备无法启动 3D 棋盘</div>}
    >
      <color attach="background" args={["#101615"]} />
      <fog attach="fog" args={["#101615", 25, 48]} />
      <Atmosphere effects={props.effects}/>
      <hemisphereLight args={["#d5ddd5", "#171b19", 1.65]} />
      <directionalLight
        position={[5.5, 11, 6.5]}
        intensity={2.35}
        color="#f2dfbd"
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-camera-near={1}
        shadow-camera-far={28}
        shadow-camera-left={-8}
        shadow-camera-right={8}
        shadow-camera-top={8}
        shadow-camera-bottom={-8}
        shadow-normalBias={.012}
      />
      <pointLight position={[-7, 3.8, 6]} color="#b84c3d" intensity={8} distance={11} decay={2} />
      <pointLight position={[7, 3.4, -6]} color="#8fa9a0" intensity={7} distance={11} decay={2} />
      <Suspense fallback={null}>
        <Battlefield {...props} />
      </Suspense>
      <CameraRig mode={props.cameraMode} reset={props.cameraReset} />
      {new URLSearchParams(window.location.search).get('audit')==='1'&&<SceneDiagnostics/>}
    </Canvas>
  );
}
