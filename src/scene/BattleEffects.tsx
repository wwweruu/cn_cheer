import { useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { Group, InstancedMesh, Mesh, MeshBasicMaterial, Object3D, Vector3 } from 'three';
import { boardToWorld } from '../game/coordinates';
import type { EffectLevel, MovePlayback } from '../game/types';
import { CAPTURE, clamp, playbackSeconds } from './moveTimeline';

function CaptureEffects({move,level}:{move:MovePlayback;level:EffectLevel}) {
  const root=useRef<Group>(null),particles=useRef<InstancedMesh>(null),ring=useRef<Mesh>(null),projectile=useRef<Mesh>(null),flash=useRef<Mesh>(null);
  const dummy=useMemo(()=>new Object3D(),[]);
  const from=boardToWorld(move.from),to=boardToWorld(move.to);
  const count=level==='full'?24:10;
  const cannon=move.piece.type==='cannon';
  const {scene}=useThree();
  const launchOrigin=useRef<Vector3|null>(null);
  useFrame(()=>{
    const t=playbackSeconds(move),impact=t-CAPTURE.contact,p=clamp(impact/.62);
    if(root.current)root.current.visible=impact>=0&&p<1;
    if(particles.current){
      for(let i=0;i<count;i++){
        const a=i*2.39996,speed=.5+(i%5)*.12,r=p*speed;
        dummy.position.set(Math.cos(a)*r,.1+Math.sin(p*Math.PI)*(.3+(i%4)*.1),Math.sin(a)*r);
        dummy.rotation.set(p*6+i,p*4+i,0);dummy.scale.setScalar((.018+i%3*.008)*(1-p));dummy.updateMatrix();particles.current.setMatrixAt(i,dummy.matrix);
      }
      particles.current.instanceMatrix.needsUpdate=true;
      (particles.current.material as MeshBasicMaterial).opacity=(1-p)*.8;
    }
    if(ring.current){ring.current.scale.setScalar(.3+p*1.7);(ring.current.material as MeshBasicMaterial).opacity=(1-p)*.45;}
    if(projectile.current){
      const q=clamp((t-CAPTURE.launch)/(CAPTURE.contact-CAPTURE.launch));
      projectile.current.visible=cannon&&t>=CAPTURE.launch&&t<CAPTURE.contact;
      if(projectile.current.visible&&!launchOrigin.current){
        const muzzle=scene.getObjectByName(`piece-${move.piece.id}`)?.getObjectByName('Muzzle');
        launchOrigin.current=muzzle?.getWorldPosition(new Vector3())??new Vector3(from[0],.95,from[2]);
        projectile.current.userData.launchOrigin=launchOrigin.current.toArray();
      }
      const origin=launchOrigin.current;
      if(origin)projectile.current.position.set(origin.x+(to[0]-origin.x)*q,origin.y+(.95-origin.y)*q+Math.sin(q*Math.PI)*Math.min(2,Math.hypot(to[0]-origin.x,to[2]-origin.z)*.32),origin.z+(to[2]-origin.z)*q);
    }
    if(flash.current){
      const age=t-CAPTURE.launch;
      flash.current.visible=cannon&&move.piece.camp==='red'&&age>=0&&age<.12&&!!launchOrigin.current;
      if(launchOrigin.current)flash.current.position.copy(launchOrigin.current);
      flash.current.scale.setScalar(.5+clamp(age/.12)*1.2);
      (flash.current.material as MeshBasicMaterial).opacity=(1-clamp(age/.12))*.9;
    }
  });
  return <>
    <mesh ref={projectile} name="capture-projectile" visible={false}><icosahedronGeometry args={[.065,1]}/><meshStandardMaterial color={move.piece.camp==='red'?'#332b24':'#726958'} roughness={.8}/></mesh>
    <mesh ref={flash} name="cannon-muzzle-flash" visible={false}><icosahedronGeometry args={[.09,1]}/><meshBasicMaterial color="#ffdc91" transparent depthWrite={false} toneMapped={false}/></mesh>
    <group ref={root} position={[to[0],.28,to[2]]} visible={false}>
      <mesh ref={ring} rotation={[-Math.PI/2,0,0]}><ringGeometry args={[.3,.34,32]}/><meshBasicMaterial color="#c6ad77" transparent depthWrite={false}/></mesh>
      <instancedMesh ref={particles} args={[undefined,undefined,count]} frustumCulled={false}><octahedronGeometry args={[1,0]}/><meshBasicMaterial color={cannon?'#cfad78':'#d4c49c'} transparent depthWrite={false}/></instancedMesh>
    </group>
  </>;
}

export function BattleEffects({move,level}:{move:MovePlayback|null;level:EffectLevel}) {
  return move?.captured&&level!=='off'&&move.effectLevel!=='off'?<CaptureEffects key={move.token} move={move} level={level}/>:null;
}
