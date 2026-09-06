import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { CanvasTexture, InstancedBufferAttribute, InstancedMesh, Matrix4, MeshBasicMaterial, PlaneGeometry, SRGBColorSpace, Vector3 } from "three";
import type { Piece } from "../game/types";

/** All 32 deterministic nameplates share a single atlas and draw. */
export function PieceNameplates({pieces}:{pieces:Piece[]}) {
  const mesh=useRef<InstancedMesh>(null);const {scene}=useThree();
  const resources=useMemo(()=>{
    const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=512;
    const context=canvas.getContext('2d')!;
    const glyphs=['帅','仕','相','马','车','炮','兵','将','士','象','马','车','炮','卒'];
    glyphs.forEach((glyph,index)=>{
      const x=index%4*256,y=Math.floor(index/4)*128,red=index<7;
      context.fillStyle=red?'#392b27':'#242b2b';context.fillRect(x,y,256,128);
      context.strokeStyle=red?'#b69958':'#98a29c';context.lineWidth=5;context.strokeRect(x+4,y+4,248,120);
      context.fillStyle=red?'#e0c78c':'#d2d8d3';context.font='700 106px KaiTi, STKaiti, serif';context.textAlign='center';context.textBaseline='middle';context.fillText(glyph,x+128,y+70);
    });
    const texture=new CanvasTexture(canvas);texture.colorSpace=SRGBColorSpace;
    const geometry=new PlaneGeometry(1,1);const offsets=new InstancedBufferAttribute(new Float32Array(64),2);geometry.setAttribute('plateOffset',offsets);
    const material=new MeshBasicMaterial({map:texture,toneMapped:false});
    material.onBeforeCompile=shader=>{
      shader.vertexShader='attribute vec2 plateOffset;\n'+shader.vertexShader;
      shader.vertexShader=shader.vertexShader.replace('#include <uv_vertex>','#include <uv_vertex>\n vMapUv = vMapUv * vec2(0.25, 0.25) + plateOffset;');
    };
    return {texture,geometry,material,offsets};
  },[]);
  const transform=useMemo(()=>new Matrix4(),[]),translation=useMemo(()=>new Matrix4(),[]),scale=useMemo(()=>new Vector3(),[]);
  const inverseWorld=useMemo(()=>new Matrix4(),[]);
  useEffect(()=>()=>{resources.texture.dispose();resources.geometry.dispose();resources.material.dispose();},[resources]);
  useFrame(()=>{
    if(!mesh.current)return;let count=0;
    mesh.current.updateWorldMatrix(true,false);
    inverseWorld.copy(mesh.current.matrixWorld).invert();
    for(const piece of pieces) {
      const group=scene.getObjectByName(`piece-${piece.id}`);if(!group||!group.visible||group.userData.status!=='ready'||(group.userData.motion?.opacity??1)<.8)continue;
      const {baseHeight,front}=group.userData.nameplate;
      group.updateWorldMatrix(true,false);
      transform.makeRotationY(piece.camp==='red'?Math.PI:0);
      transform.multiply(translation.makeTranslation(0,baseHeight*.51,front+.006));
      transform.scale(scale.set(.21,Math.min(.10,baseHeight*.8),1));transform.premultiply(group.matrixWorld);
      transform.premultiply(inverseWorld);
      mesh.current.setMatrixAt(count,transform);
      const tile=['general','advisor','elephant','horse','chariot','cannon','soldier'].indexOf(piece.type)+(piece.camp==='red'?0:7);
      resources.offsets.setXY(count,tile%4*.25,.75-Math.floor(tile/4)*.25);count++;
    }
    mesh.current.count=count;mesh.current.instanceMatrix.needsUpdate=true;
    (mesh.current.geometry.getAttribute('plateOffset') as InstancedBufferAttribute).needsUpdate=true;
  });
  return <instancedMesh ref={mesh} args={[resources.geometry,resources.material,32]} frustumCulled={false} raycast={()=>null} dispose={null}/>;
}
