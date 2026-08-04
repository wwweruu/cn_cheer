import { Suspense, useEffect, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows, OrbitControls } from "@react-three/drei";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { Group, PCFShadowMap, Vector3 } from "three";
import type {
  CameraMode,
  EffectLevel,
  MoveRecord,
  Piece,
  Position,
} from "../game/types";
import { ArmoredPiece } from "./ArmoredPiece";
import { BattleEffects } from "./BattleEffects";
import { BattlefieldBoard } from "./BattlefieldBoard";

interface GameSceneProps {
  pieces: Piece[];
  selected: Position | null;
  legalMoves: Position[];
  moves: MoveRecord[];
  animation: MoveRecord | null;
  effects: EffectLevel;
  cameraShake: boolean;
  cameraMode: CameraMode;
  cameraReset: number;
  onPositionClick: (position: Position) => void;
  onMoveComplete: () => void;
}

function CameraRig({ mode, reset }: { mode: CameraMode; reset: number }) {
  const { camera, size } = useThree();
  const controls = useRef<OrbitControlsImpl>(null);
  const desiredPosition = useRef(new Vector3(8.4, 11.2, 14.3));
  const desiredTarget = useRef(new Vector3(0, 0.45, 0));
  const transitioning = useRef(true);

  useEffect(() => {
    const portrait = size.width / size.height < 0.85;
    const landscapeDistanceScale = !portrait && size.height <= 760 ? 1.1 : 1;
    desiredPosition.current.set(
      mode === "top" ? 0.01 : portrait ? 0.01 : 8.4 * landscapeDistanceScale,
      mode === "top"
        ? (portrait ? 26 : 17.2 * landscapeDistanceScale)
        : portrait
          ? 23
          : 0.45 + (11.2 - 0.45) * landscapeDistanceScale,
      mode === "top" ? 0.01 : portrait ? 10 : 14.3 * landscapeDistanceScale,
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

function Banner({ side, position }: { side: "red" | "black"; position: [number, number, number] }) {
  const red = side === "red";
  return (
    <group position={position} rotation={[0, position[0] < 0 ? 0.18 : -0.18, 0]}>
      <mesh position={[0, 1.25, 0]} castShadow>
        <cylinderGeometry args={[0.035, 0.045, 2.5, 8]} />
        <meshStandardMaterial color="#7d7465" metalness={0.68} roughness={0.28} />
      </mesh>
      <mesh position={[0.43, 2.15, 0]} castShadow>
        <boxGeometry args={[0.88, 0.035, 0.035]} />
        <meshStandardMaterial color="#8f816a" metalness={0.58} roughness={0.34} />
      </mesh>
      <mesh position={[0.45, 1.74, 0]} castShadow>
        <planeGeometry args={[0.8, 0.75, 1, 1]} />
        <meshStandardMaterial
          color={red ? "#772725" : "#263432"}
          roughness={0.78}
          metalness={0.04}
          side={2}
        />
      </mesh>
    </group>
  );
}

function StageDecor() {
  return (
    <group>
      <mesh position={[0, -0.43, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[42, 42]} />
        <meshStandardMaterial color="#121817" roughness={0.96} metalness={0.02} />
      </mesh>
      <Banner side="black" position={[-6.6, -0.4, -5.4]} />
      <Banner side="black" position={[6.6, -0.4, -5.4]} />
      <Banner side="red" position={[-6.6, -0.4, 5.4]} />
      <Banner side="red" position={[6.6, -0.4, 5.4]} />
      {[-8.4, 8.4].flatMap((x) =>
        [-7.2, 0, 7.2].map((z) => (
          <mesh key={`${x}-${z}`} position={[x, -0.29, z]} rotation={[0, (x + z) * 0.07, 0]}>
            <boxGeometry args={[2.8, 0.14, 1.7]} />
            <meshStandardMaterial color="#1d2422" roughness={0.88} />
          </mesh>
        )),
      )}
    </group>
  );
}

function Battlefield({
  pieces,
  selected,
  legalMoves,
  moves,
  animation,
  effects,
  cameraShake,
  onPositionClick,
  onMoveComplete,
}: Omit<GameSceneProps, "cameraMode" | "cameraReset">) {
  const root = useRef<Group>(null);
  const shakeStarted = useRef(0);
  const visiblePieces = animation?.captured
    ? [...pieces, animation.captured]
    : pieces;

  useEffect(() => {
    if (animation?.captured) shakeStarted.current = performance.now();
  }, [animation]);

  useFrame(() => {
    if (!root.current) return;
    if (!cameraShake || !animation?.captured || effects !== "full") {
      root.current.position.set(0, 0, 0);
      return;
    }
    const elapsed = (performance.now() - shakeStarted.current) / 1000;
    const strength = Math.max(0, 1 - elapsed / 0.42) * 0.035;
    root.current.position.set(
      Math.sin(elapsed * 78) * strength,
      Math.sin(elapsed * 54) * strength * 0.4,
      Math.cos(elapsed * 66) * strength,
    );
  });

  return (
    <group ref={root}>
      <StageDecor />
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
          onClick={() => onPositionClick(piece.position)}
          onMoveComplete={onMoveComplete}
        />
      ))}
      <BattleEffects move={animation} level={effects} />
      <ContactShadows
        position={[0, 0.04, 0]}
        opacity={0.38}
        scale={13}
        blur={2.2}
        far={4.5}
        resolution={512}
      />
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
      fallback={<div className="canvas-fallback">当前设备无法启动 3D 棋盘</div>}
    >
      <color attach="background" args={["#101615"]} />
      <fog attach="fog" args={["#101615", 17, 38]} />
      <hemisphereLight args={["#d5ddd5", "#171b19", 1.45]} />
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
      />
      <pointLight position={[-7, 3.8, 6]} color="#b84c3d" intensity={8} distance={11} decay={2} />
      <pointLight position={[7, 3.4, -6]} color="#8fa9a0" intensity={7} distance={11} decay={2} />
      <Suspense fallback={null}>
        <Battlefield {...props} />
      </Suspense>
      <CameraRig mode={props.cameraMode} reset={props.cameraReset} />
    </Canvas>
  );
}
