import { useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import {
  CanvasTexture,
  DoubleSide,
  LinearFilter,
  Mesh,
  SRGBColorSpace,
  Vector3,
} from "three";
import { BOARD_SPACING, boardToWorld, positionKey } from "../game/coordinates";
import type { MoveRecord, Position } from "../game/types";

interface BattlefieldBoardProps {
  selected: Position | null;
  legalMoves: Position[];
  lastMove: MoveRecord | null;
  onPositionClick: (position: Position) => void;
}

const lineColor = "#bcb09a";

function makeRiverTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 192;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("无法创建楚河汉界纹理");
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "rgba(200, 194, 172, .82)";
  context.font = "600 80px KaiTi, STKaiti, serif";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText("楚  河", 260, 101);
  context.fillText("汉  界", 764, 101);
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.minFilter = LinearFilter;
  texture.magFilter = LinearFilter;
  return texture;
}

function GridLines() {
  const xMin = -4 * BOARD_SPACING;
  const xMax = 4 * BOARD_SPACING;
  const zMin = -4.5 * BOARD_SPACING;
  const zMax = 4.5 * BOARD_SPACING;
  const riverNorth = -0.5 * BOARD_SPACING;
  const riverSouth = 0.5 * BOARD_SPACING;

  const lines = useMemo(() => {
    const result: [number, number, number][][] = [];
    for (let rank = 0; rank < 10; rank += 1) {
      const z = (rank - 4.5) * BOARD_SPACING;
      result.push([
        [xMin, 0.28, z],
        [xMax, 0.28, z],
      ]);
    }
    for (let file = 0; file < 9; file += 1) {
      const x = (file - 4) * BOARD_SPACING;
      if (file === 0 || file === 8) {
        result.push([
          [x, 0.28, zMin],
          [x, 0.28, zMax],
        ]);
      } else {
        result.push([
          [x, 0.28, zMin],
          [x, 0.28, riverNorth],
        ]);
        result.push([
          [x, 0.28, riverSouth],
          [x, 0.28, zMax],
        ]);
      }
    }
    const palace = (fromRank: number, toRank: number) => {
      const startZ = (fromRank - 4.5) * BOARD_SPACING;
      const endZ = (toRank - 4.5) * BOARD_SPACING;
      const leftX = -BOARD_SPACING;
      const rightX = BOARD_SPACING;
      result.push([
        [leftX, 0.285, startZ],
        [rightX, 0.285, endZ],
      ]);
      result.push([
        [rightX, 0.285, startZ],
        [leftX, 0.285, endZ],
      ]);
    };
    palace(0, 2);
    palace(7, 9);
    return result;
  }, [riverNorth, riverSouth, xMax, xMin, zMax, zMin]);

  return (
    <>
      {lines.map((points, index) => (
        <Line
          key={index}
          points={points}
          color={lineColor}
          lineWidth={1.25}
          transparent
          opacity={0.83}
        />
      ))}
    </>
  );
}

function LastMoveMarker({ position }: { position: Position }) {
  const [x, , z] = boardToWorld(position);
  return (
    <mesh position={[x, 0.295, z]} rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[0.29, 0.35, 32]} />
      <meshBasicMaterial color="#c7b67d" transparent opacity={0.56} depthWrite={false} />
    </mesh>
  );
}

function LegalMoveHitTarget({
  position,
  onClick,
}: {
  position: Position;
  onClick: () => void;
}) {
  const mesh = useRef<Mesh>(null);
  const { camera } = useThree();
  const file = position.file;
  const rank = position.rank;
  const boardPoint = useMemo(() => {
    const [x, , z] = boardToWorld({ file, rank });
    return new Vector3(x, 0.34, z);
  }, [file, rank]);
  const direction = useMemo(() => new Vector3(), []);

  useFrame(() => {
    if (!mesh.current) return;
    direction.copy(camera.position).sub(boardPoint).normalize();
    mesh.current.position.copy(boardPoint).addScaledVector(direction, 2.4);
  });

  return (
    <mesh
      ref={mesh}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
    >
      <sphereGeometry args={[0.46, 12, 8]} />
      <meshBasicMaterial transparent opacity={0} depthWrite={false} />
    </mesh>
  );
}

export function BattlefieldBoard({
  selected,
  legalMoves,
  lastMove,
  onPositionClick,
}: BattlefieldBoardProps) {
  const riverTexture = useMemo(() => makeRiverTexture(), []);
  const legalKeys = useMemo(() => new Set(legalMoves.map(positionKey)), [legalMoves]);
  const intersections = useMemo(() => {
    const result: Position[] = [];
    for (let rank = 0; rank < 10; rank += 1) {
      for (let file = 0; file < 9; file += 1) result.push({ file, rank });
    }
    return result;
  }, []);

  return (
    <group>
      <mesh position={[0, -0.08, 0]} castShadow receiveShadow>
        <boxGeometry args={[10.25, 0.62, 11.35]} />
        <meshStandardMaterial color="#151b1a" metalness={0.34} roughness={0.54} />
      </mesh>
      <mesh position={[0, 0.16, 0]} receiveShadow>
        <boxGeometry args={[9.55, 0.18, 10.65]} />
        <meshStandardMaterial color="#343a35" metalness={0.08} roughness={0.73} />
      </mesh>
      <mesh position={[0, 0.265, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[8.45, 0.96]} />
        <meshStandardMaterial color="#1c2b29" metalness={0.22} roughness={0.52} />
      </mesh>
      <mesh position={[0, 0.288, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[8.05, 0.82]} />
        <meshBasicMaterial
          map={riverTexture}
          transparent
          opacity={0.9}
          side={DoubleSide}
          toneMapped={false}
          depthWrite={false}
        />
      </mesh>
      <GridLines />

      {[
        [-4.86, 0.25, 0, 0.2, 10.9],
        [4.86, 0.25, 0, 0.2, 10.9],
        [0, 0.25, -5.4, 9.55, 0.2],
        [0, 0.25, 5.4, 9.55, 0.2],
      ].map(([x, y, z, width, depth], index) => (
        <mesh key={index} position={[x, y, z]} castShadow>
          <boxGeometry args={[width, 0.34, depth]} />
          <meshStandardMaterial color="#716758" metalness={0.62} roughness={0.32} />
        </mesh>
      ))}

      {lastMove && (
        <>
          <LastMoveMarker position={lastMove.from} />
          <LastMoveMarker position={lastMove.to} />
        </>
      )}

      {intersections.map((position) => {
        const [x, , z] = boardToWorld(position);
        const legal = legalKeys.has(positionKey(position));
        const isSelected = selected && positionKey(selected) === positionKey(position);
        return (
          <group key={positionKey(position)} position={[x, 0.3, z]}>
            {legal && (
              <>
                <mesh rotation={[-Math.PI / 2, 0, 0]}>
                  <circleGeometry args={[0.14, 24]} />
                  <meshBasicMaterial
                    color="#d7c58c"
                    transparent
                    opacity={0.88}
                    depthWrite={false}
                  />
                </mesh>
                <mesh position={[0, 0.012, 0]} rotation={[-Math.PI / 2, 0, 0]}>
                  <ringGeometry args={[0.2, 0.25, 28]} />
                  <meshBasicMaterial
                    color="#d7c58c"
                    transparent
                    opacity={0.46}
                    depthWrite={false}
                  />
                </mesh>
              </>
            )}
            {isSelected && (
              <mesh position={[0, 0.006, 0]} rotation={[-Math.PI / 2, 0, 0]}>
                <ringGeometry args={[0.38, 0.46, 36]} />
                <meshBasicMaterial color="#db755f" transparent opacity={0.78} />
              </mesh>
            )}
            <mesh
              position={[0, 0.16, 0]}
              onClick={(event) => {
                event.stopPropagation();
                onPositionClick(position);
              }}
            >
              <cylinderGeometry args={[0.48, 0.48, 0.36, 16]} />
              <meshBasicMaterial transparent opacity={0} depthWrite={false} />
            </mesh>
          </group>
        );
      })}
      {legalMoves.map((position) => (
        <LegalMoveHitTarget
          key={`legal-hit-${positionKey(position)}`}
          position={position}
          onClick={() => onPositionClick(position)}
        />
      ))}
    </group>
  );
}
