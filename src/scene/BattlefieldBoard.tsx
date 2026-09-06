import { useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import {
  CanvasTexture,
  BufferGeometry,
  Float32BufferAttribute,
  DoubleSide,
  LinearFilter,
  Mesh,
  SRGBColorSpace,
  Vector3,
} from "three";
import { BOARD_SPACING, boardToWorld, positionKey } from "../game/coordinates";
import type { MoveRecord, Position } from "../game/types";
import { BattlefieldTerrain } from "./BattlefieldTerrain";
import { Surface } from "./Surface";

interface BattlefieldBoardProps {
  selected: Position | null;
  legalMoves: Position[];
  lastMove: MoveRecord | null;
  onPositionClick: (position: Position) => void;
}

function makeRiverTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 1024;
  canvas.height = 192;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("无法创建楚河汉界纹理");
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "rgba(216, 206, 176, .95)";
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
        [xMin, 0.258, z],
        [xMax, 0.258, z],
      ]);
    }
    for (let file = 0; file < 9; file += 1) {
      const x = (file - 4) * BOARD_SPACING;
      if (file === 0 || file === 8) {
        result.push([
          [x, 0.258, zMin],
          [x, 0.258, zMax],
        ]);
      } else {
        result.push([
          [x, 0.258, zMin],
          [x, 0.258, riverNorth],
        ]);
        result.push([
          [x, 0.258, riverSouth],
          [x, 0.258, zMax],
        ]);
      }
    }
    const palace = (fromRank: number, toRank: number) => {
      const startZ = (fromRank - 4.5) * BOARD_SPACING;
      const endZ = (toRank - 4.5) * BOARD_SPACING;
      const leftX = -BOARD_SPACING;
      const rightX = BOARD_SPACING;
      result.push([
        [leftX, 0.259, startZ],
        [rightX, 0.259, endZ],
      ]);
      result.push([
        [rightX, 0.259, startZ],
        [leftX, 0.259, endZ],
      ]);
    };
    palace(0, 2);
    palace(7, 9);
    return result;
  }, [riverNorth, riverSouth, xMax, xMin, zMax, zMin]);

  const geometry = useMemo(() => {
    const vertices: number[] = [],uvs:number[]=[];
    for (const [a,b] of lines) {
      const dx=b[0]-a[0], dz=b[2]-a[2], length=Math.hypot(dx,dz);
      const px=-dz/length*.082, pz=dx/length*.082;
      const corners=[[a[0]+px,a[1],a[2]+pz],[a[0]-px,a[1],a[2]-pz],[b[0]-px,b[1],b[2]-pz],[b[0]+px,b[1],b[2]+pz]];
      const uv=[[0,0],[1,0],[1,length*2],[0,length*2]];
      for (const index of [0,1,2,0,2,3]) {vertices.push(...corners[index]);uvs.push(...uv[index]);}
    }
    const result=new BufferGeometry();result.setAttribute("position",new Float32BufferAttribute(vertices,3));result.setAttribute('uv',new Float32BufferAttribute(uvs,2));result.computeVertexNormals();return result;
  }, [lines]);
  return <mesh geometry={geometry} renderOrder={-1} receiveShadow><Surface asset="battlefield_earth" tint="#ead9b9" wornPath/></mesh>;
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
      visible={false}
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
      <BattlefieldTerrain />
      <mesh position={[0, 0.07, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[8.05, 0.6]} />
        <meshBasicMaterial
          map={riverTexture}
          transparent
          opacity={0.55}
          side={DoubleSide}
          toneMapped={false}
          depthWrite={false}
        />
      </mesh>
      <GridLines />


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
              visible={false}
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
