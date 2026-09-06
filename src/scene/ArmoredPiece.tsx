import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { AnimationMixer, Box3, CanvasTexture, Group, LinearFilter, Mesh, SkinnedMesh, SRGBColorSpace, Vector3 } from "three";
import { clone } from 'three/addons/utils/SkeletonUtils.js';
import { attackerPosition, CAPTURE, clamp, ease, motionPose, playbackSeconds } from './moveTimeline';
import { boardToWorld } from "../game/coordinates";
import { useRuntimeAsset } from "../assets/runtimeAssets";
import { choosePieceTier, type ModelTier } from "../assets/quality";
import type { EffectLevel, ModelQuality, MovePlayback, Piece, PieceType } from "../game/types";

interface ArmoredPieceProps {
  piece: Piece; selected: boolean; move: MovePlayback | null; effects: EffectLevel; quality: ModelQuality;
  onClick: () => void;
}
const LABELS: Record<PieceType, { red: string; black: string }> = {
  general: { red: "帅", black: "将" }, advisor: { red: "仕", black: "士" },
  elephant: { red: "相", black: "象" }, horse: { red: "马", black: "马" },
  chariot: { red: "车", black: "车" }, cannon: { red: "炮", black: "炮" }, soldier: { red: "兵", black: "卒" },
};
const labels = new Map<string, CanvasTexture>();
function labelTexture(piece: Piece) {
  const key = `${piece.type}_${piece.camp}`;
  if (labels.has(key)) return labels.get(key)!;
  const canvas = document.createElement("canvas");
  canvas.width = 256; canvas.height = 128;
  const context = canvas.getContext("2d")!;
  context.fillStyle = piece.camp === "red" ? "#392b27" : "#242b2b";
  context.fillRect(0, 0, 256, 128);
  context.strokeStyle = piece.camp === "red" ? "#b69958" : "#98a29c";
  context.lineWidth = 5; context.strokeRect(4, 4, 248, 120);
  context.fillStyle = piece.camp === "red" ? "#e0c78c" : "#d2d8d3";
  context.font = "700 106px KaiTi, STKaiti, serif";
  context.textAlign = "center"; context.textBaseline = "middle";
  context.fillText(LABELS[piece.type][piece.camp], 128, 70);
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace; texture.minFilter = LinearFilter;
  labels.set(key, texture); return texture;
}
function modelDimensions(scene: Group) {
  if (scene.userData.pieceDimensions) return scene.userData.pieceDimensions as { height: number; front: number; baseHeight: number };
  scene.updateMatrixWorld(true);
  const box = new Box3().setFromObject(scene);
  const height = box.max.y-box.min.y;
  const baseHeight = Math.min(.13, height*.075);
  const point = new Vector3(); let front = 0;
  scene.traverse(object => {
    if (!(object instanceof Mesh)) return;
    const position = object.geometry.getAttribute("position");
    for (let i=0;i<position.count;i++) {
      object.getVertexPosition(i,point).applyMatrix4(object.matrixWorld);
      if (point.y<baseHeight && Math.abs(point.x)<.12) front=Math.max(front,point.z);
    }
  });
  return scene.userData.pieceDimensions = { height, front, baseHeight };
}

export function ArmoredPiece({ piece, selected, move, effects, quality, onClick }: ArmoredPieceProps) {
  const group = useRef<Group>(null);
  const [hovered, setHovered] = useState(false);
  const [tier, setTier] = useState<ModelTier>("distant");
  const lastTierCheck = useRef(0);
  const { camera, size } = useThree();
  const asset = useRuntimeAsset("motion", `${piece.type}_${piece.camp}`, tier);
  const animated = useMemo(() => {
    if(!asset.value)return null;
    const model=clone(asset.value);const mixer=new AnimationMixer(model);
    const actions=Object.fromEntries(asset.value.animations.map(clip=>{
      const action=mixer.clipAction(clip);action.play();action.paused=true;return [clip.name,action];
    }));
    const materials:import('three').Material[]=[];
    model.traverse(object=>{if(object instanceof Mesh){
      object.frustumCulled=false;
      const copies=(Array.isArray(object.material)?object.material:[object.material]).map(material=>{const copy=material.clone();materials.push(copy);return copy;});
      object.material=Array.isArray(object.material)?copies:copies[0];
    }});
    return {model,mixer,actions,materials};
  },[asset.value]);
  useEffect(()=>{
    if(!animated)return;
    Object.values(animated.actions).forEach(action=>action.play());
    return ()=>{animated.mixer.stopAllAction();animated.materials.forEach(material=>material.dispose());animated.model.traverse(object=>{if(object instanceof SkinnedMesh)object.skeleton.dispose();});};
  },[animated]);
  const model=animated?.model;
  const dimensions = useMemo(() => asset.value ? modelDimensions(asset.value) : { height: 1.5, front: .42, baseHeight: .1 }, [asset.value]);
  const label = useMemo(() => labelTexture(piece), [piece]);
  const projected = useMemo(() => [new Vector3(), new Vector3()], []);
  const activeMove = move?.piece.id === piece.id ? move : null;
  const red = piece.camp === "red";
  useFrame(({ clock }) => {
    if (!group.current) return;
    const target = boardToWorld(piece.position);
    let [x, , z] = target; let y = .25;
    const t=move?playbackSeconds(move):0;
    const captured=move?.captured?.id===piece.id;
    let opacity=1;
    if (activeMove) {
      [x,y,z]=attackerPosition(activeMove,t);
      const from=boardToWorld(activeMove.from);
      // The red cannon's barrel faces the opposite way to its standing crew.
      const barrelFacing=piece.type==='cannon'&&red?Math.PI:0;
      let angle=Math.atan2(target[0]-from[0],target[2]-from[2])-(red?Math.PI:0)+barrelFacing;
      angle=Math.atan2(Math.sin(angle),Math.cos(angle));
      const turn=activeMove.captured?ease(t/.18)*(1-ease((t-CAPTURE.settle)/(CAPTURE.end-CAPTURE.settle))):Math.sin(Math.PI*clamp(t/.65));
      group.current.rotation.y=activeMove.effectLevel==='off'?0:angle*turn;
    } else {
      group.current.rotation.y=0;
    }
    if(captured&&move?.effectLevel!=='off')opacity=1-ease((t-CAPTURE.fade)/(CAPTURE.gone-CAPTURE.fade));
    group.current.visible=opacity>.001;
    const pose=motionPose(move,piece.id,t);
    if(animated){
      const phase=(piece.id*.731)%4;
      for(const [name,action] of Object.entries(animated.actions)){
        action.enabled=true;
        const duration=action.getClip().duration;
        action.time=name==='idle'?(effects==='off'?0:(clock.elapsedTime*.72+phase)%duration):Math.min(duration-.001,pose.progress*duration);
        action.setEffectiveWeight(name==='idle'?1-pose.weight:name===pose.clip?pose.weight:0);
      }
      animated.mixer.update(0);
      animated.materials.forEach(material=>{
        const transparent=opacity<.999;
        if(material.transparent!==transparent){material.transparent=transparent;material.needsUpdate=true;}
        material.opacity=opacity;material.depthWrite=!transparent;
      });
    }
    group.current.userData.motion={clip:pose.weight>.1?pose.clip:'idle',progress:pose.progress,opacity,token:move?.token??null};
    const targetScale=selected?1.025:hovered?1.012:1;
    group.current.scale.setScalar(group.current.scale.x+(targetScale-group.current.scale.x)*.18);
    group.current.position.set(x,y,z);
    if (clock.elapsedTime-lastTierCheck.current>.5) {
      lastTierCheck.current=clock.elapsedTime;
      projected[0].set(x,y,z).project(camera); projected[1].set(x,y+dimensions.height,z).project(camera);
      const pixels=Math.abs(projected[0].y-projected[1].y)*size.height/2;
      const mobile=matchMedia("(pointer: coarse)").matches || size.width<700;
      const next=choosePieceTier(pixels,selected,quality,mobile,tier);
      if (next!==tier) setTier(next);
    }
  });
  return <group ref={group} name={`piece-${piece.id}`} userData={{ pieceId: piece.id, asset: `${piece.type}_${piece.camp}`, tier, status: asset.status, nameplate:dimensions }}
    onClick={event=>{event.stopPropagation();onClick();}}
    onPointerEnter={event=>{event.stopPropagation();setHovered(true);}} onPointerLeave={()=>setHovered(false)}>
    {(selected||hovered) && <mesh position={[0,.015,0]} rotation={[-Math.PI/2,0,0]}>
      <ringGeometry args={[.4,.49,40]}/><meshBasicMaterial color={selected?(red?"#df7a62":"#9cb5ad"):"#c8bfa9"} transparent opacity={.82}/>
    </mesh>}
    {model ? <group rotation={[0,red?Math.PI:0,0]} dispose={null}>
      <primitive object={model} dispose={null}/>
    </group> : <group>
      <mesh position={[0,.105,0]} castShadow receiveShadow><cylinderGeometry args={[.40,.44,.21,24]}/><meshStandardMaterial color={red?"#642e29":"#303c39"} metalness={.3} roughness={.65}/></mesh>
      <mesh position={[0,.214,0]} rotation={[-Math.PI/2,0,red?0:Math.PI]}><planeGeometry args={[.42,.23]}/><meshBasicMaterial map={label}/></mesh>
    </group>}
    <mesh position={[0,.5,0]} visible={false}><cylinderGeometry args={[.47,.47,1,12]}/><meshBasicMaterial/></mesh>
  </group>;
}
