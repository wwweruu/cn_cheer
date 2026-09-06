import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Mesh, SkinnedMesh, Texture, Vector3 } from "three";
import { runtimeAssets } from "../assets/runtimeAssets";

declare global { interface Window { __CHESS_DIAGNOSTICS__?: Record<string,unknown> } }

/** Enabled only by ?audit=1; counts all shadow and main draws in the same frame. */
export function SceneDiagnostics() {
  const times=useRef<number[]>([]);const frame=useRef(0);
  useFrame(({gl,scene,camera,size},delta)=>{
    gl.info.autoReset=false;gl.info.reset();gl.render(scene,camera);
    times.current.push(delta*1000);if(times.current.length>240)times.current.shift();
    if(++frame.current%(scene.getObjectByName('capture-projectile')?3:12)!==0)return;
    const sorted=[...times.current].sort((a,b)=>a-b);
    const pieces:Array<Record<string,unknown>>=[];
    scene.traverse(o=>{if(o.name.startsWith('piece-')){
      const bones:number[]=[];
      o.traverse(child=>{if(child instanceof SkinnedMesh)child.skeleton.bones.forEach(bone=>bones.push(...bone.quaternion.toArray(),...bone.position.toArray()));});
      const muzzle=o.getObjectByName('Muzzle');
      pieces.push({...o.userData,position:o.position.toArray(),muzzle:muzzle?.getWorldPosition(new Vector3()).toArray(),poseSignature:bones.reduce((sum,value,i)=>sum+value*(i%17+1),0)});
    }});
    const context=gl.getContext(),extension=context.getExtension('WEBGL_debug_renderer_info');
    const points=[];
    for(let rank=0;rank<10;rank++)for(let file=0;file<9;file++) {
      const p=new Vector3((file-4)*1.05,.43,(rank-4.5)*1.05).project(camera);
      points.push({file,rank,x:(p.x+1)*size.width/2,y:(1-p.y)*size.height/2});
    }
    const sources=new Set<number>();let textureBytes=0;
    const inspect=(texture:Texture)=>{
      if(sources.has(texture.source.id))return;sources.add(texture.source.id);
      const mipBytes=texture.mipmaps.reduce((sum,mip)=>sum+('data' in mip && ArrayBuffer.isView(mip.data)?mip.data.byteLength:0),0);
      const images=Array.isArray(texture.image)?texture.image:[texture.image];
      textureBytes+=mipBytes||images.reduce((sum,image)=>sum+(image?.width??0)*(image?.height??0)*4*4/3,0);
    };
    for(const root of [...runtimeAssets.resources(),scene])root.traverse(o=>{
      if(o instanceof Mesh)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>Object.values(m).forEach(v=>{if(v instanceof Texture)inspect(v);}));
    });
    if(scene.background instanceof Texture)inspect(scene.background);if(scene.environment)inspect(scene.environment);
    const projectile=scene.getObjectByName('capture-projectile');
    window.__CHESS_DIAGNOSTICS__={frames:times.current.length,p95:sorted[Math.floor(sorted.length*.95)],median:sorted[Math.floor(sorted.length*.5)],
      projectile:projectile?{visible:projectile.visible,position:projectile.position.toArray(),...projectile.userData}:null,
      draws:gl.info.render.calls,triangles:gl.info.render.triangles,textures:gl.info.memory.textures,geometries:gl.info.memory.geometries,
      renderer:extension?context.getParameter(extension.UNMASKED_RENDERER_WEBGL):context.getParameter(context.RENDERER),
      camera:camera.position.toArray(),pieces,points,assetStats:runtimeAssets.stats(),estimatedResidentTextureMiB:textureBytes/1048576};
  },1);
  return null;
}
