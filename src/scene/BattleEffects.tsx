import { useEffect, useMemo, useRef } from "react";
import { Line } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { Group, Mesh, MeshBasicMaterial, PointLight } from "three";
import { boardToWorld } from "../game/coordinates";
import type { EffectLevel, MoveRecord } from "../game/types";

interface BattleEffectsProps {
  move: MoveRecord | null;
  level: EffectLevel;
}

const CAPTURE_IMPACT_DELAY = 0.38;
const CAPTURE_IMPACT_DURATION = 0.34;

function MoveArc({ move, level }: { move: MoveRecord; level: EffectLevel }) {
  const points = useMemo(() => {
    const from = boardToWorld(move.from);
    const to = boardToWorld(move.to);
    const height = move.piece.type === "horse" ? 1.45 : move.captured ? 0.9 : 0.52;
    return Array.from({ length: 17 }, (_, index) => {
      const progress = index / 16;
      return [
        from[0] + (to[0] - from[0]) * progress,
        0.45 + Math.sin(Math.PI * progress) * height,
        from[2] + (to[2] - from[2]) * progress,
      ] as [number, number, number];
    });
  }, [move]);

  if (level === "off") return null;
  return (
    <Line
      points={points}
      color={move.piece.camp === "red" ? "#dc7862" : "#a7c1b8"}
      lineWidth={level === "full" ? 2.4 : 1.2}
      transparent
      opacity={level === "full" ? 0.54 : 0.3}
    />
  );
}

function Impact({ move, level }: { move: MoveRecord; level: EffectLevel }) {
  const root = useRef<Group>(null);
  const ring = useRef<Mesh>(null);
  const flash = useRef<PointLight>(null);
  const materialRefs = useRef<MeshBasicMaterial[]>([]);
  const startedAt = useRef(0);
  const target = boardToWorld(move.to);
  const particleCount = level === "full" ? 18 : 8;
  const particles = useMemo(
    () =>
      Array.from({ length: particleCount }, (_, index) => {
        const angle = (index / particleCount) * Math.PI * 2;
        const speed = 0.55 + ((index * 17) % 7) * 0.08;
        return {
          angle,
          speed,
          lift: 0.45 + ((index * 11) % 5) * 0.12,
          size: 0.025 + ((index * 13) % 4) * 0.012,
        };
      }),
    [particleCount],
  );

  useEffect(() => {
    startedAt.current = performance.now();
    if (root.current) root.current.visible = false;
    if (ring.current) {
      ring.current.scale.setScalar(0.3);
      (ring.current.material as MeshBasicMaterial).opacity = 0.72;
    }
    materialRefs.current.forEach((material) => {
      material.opacity = 0.9;
    });
    if (flash.current) flash.current.intensity = 0;
  }, [move.id]);

  useFrame(() => {
    const elapsed = (performance.now() - startedAt.current) / 1000;
    if (elapsed < CAPTURE_IMPACT_DELAY) {
      if (root.current) root.current.visible = false;
      if (flash.current) flash.current.intensity = 0;
      return;
    }

    if (root.current) root.current.visible = true;
    const progress = Math.min(
      1,
      (elapsed - CAPTURE_IMPACT_DELAY) / CAPTURE_IMPACT_DURATION,
    );
    if (root.current) {
      root.current.children.slice(1).forEach((child, index) => {
        const particle = particles[index];
        if (!particle) return;
        const radius = progress * particle.speed;
        child.position.set(
          Math.cos(particle.angle) * radius,
          0.14 + Math.sin(progress * Math.PI) * particle.lift,
          Math.sin(particle.angle) * radius,
        );
        child.rotation.x += 0.12;
        child.rotation.z += 0.08;
      });
    }
    if (ring.current) {
      const scale = 0.3 + progress * 1.7;
      ring.current.scale.setScalar(scale);
      const material = ring.current.material as MeshBasicMaterial;
      material.opacity = Math.max(0, 0.72 * (1 - progress));
    }
    materialRefs.current.forEach((material) => {
      material.opacity = Math.max(0, 0.9 * (1 - progress));
    });
    if (flash.current) flash.current.intensity = 3.2 * (1 - progress);
  });

  if (!move.captured || level === "off") return null;
  const cannon = move.piece.type === "cannon";
  const color = cannon
    ? "#e89955"
    : move.piece.camp === "red"
      ? "#e67a62"
      : "#b3c9c2";

  return (
    <group ref={root} position={[target[0], 0.4, target[2]]} visible={false}>
      <mesh ref={ring} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.26, 0.34, 36]} />
        <meshBasicMaterial color={color} transparent opacity={0.72} depthWrite={false} />
      </mesh>
      {particles.map((particle, index) => (
        <mesh key={index} scale={particle.size}>
          <octahedronGeometry args={[1, 0]} />
          <meshBasicMaterial
            ref={(material) => {
              if (material && !materialRefs.current.includes(material)) {
                materialRefs.current.push(material);
              }
            }}
            color={index % 3 === 0 ? "#e8d8a7" : color}
            transparent
            opacity={0.9}
            depthWrite={false}
          />
        </mesh>
      ))}
      <pointLight ref={flash} color={color} intensity={3.2} distance={3.5} decay={2} />
    </group>
  );
}

export function BattleEffects({ move, level }: BattleEffectsProps) {
  if (!move) return null;
  return (
    <>
      <MoveArc move={move} level={level} />
      <Impact move={move} level={level} />
    </>
  );
}
