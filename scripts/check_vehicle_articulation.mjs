/* global console */
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {AnimationMixer,SkinnedMesh,Vector3} from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
globalThis.ProgressEvent??=class extends globalThis.Event {constructor(type,init){super(type);Object.assign(this,init);}};

// Exercise the exported skin and animation tracks without needing a GPU.
// The browser audit separately checks the original PBR and KTX2 assets.
const versions={horse_red:6,horse_black:4,chariot_red:6,chariot_black:4,cannon_red:6,cannon_black:7};
const report=[];
for(const [piece,version] of Object.entries(versions))for(const tier of ['desktop','mobile','distant']){
  const raw=await readFile(`assets/generated/meshy/${piece}/motion/runtime/v${version}/${piece}_${tier}.glb`);
  const length=raw.readUInt32LE(12),doc=JSON.parse(raw.subarray(20,20+length)),binary=raw.subarray(28+length);
  doc.buffers[0].uri=`data:application/octet-stream;base64,${binary.toString('base64')}`;
  delete doc.images;delete doc.textures;delete doc.materials;delete doc.samplers;
  delete doc.extensionsRequired;delete doc.extensionsUsed;
  for(const mesh of doc.meshes)for(const primitive of mesh.primitives)delete primitive.material;
  const gltf=await new GLTFLoader().parseAsync(JSON.stringify(doc),'');
  const meshes=[];gltf.scene.traverse(o=>{if(o instanceof SkinnedMesh)meshes.push(o);});
  assert.equal(meshes.length,1);const mesh=meshes[0],skeleton=mesh.skeleton;
  const sampleNames=['FixedPedestal','Weapon',piece.startsWith('horse')?'HorseFLLower':piece.startsWith('chariot')?'LeftHorseFLLower':piece==='cannon_red'?'Barrel':'ThrowArm'];
  if(piece.startsWith('chariot')||piece==='cannon_red')sampleNames.push('WheelR');
  const indices=mesh.geometry.getAttribute('skinIndex'),weights=mesh.geometry.getAttribute('skinWeight');
  const groups=Object.fromEntries(sampleNames.map(name=>{
    const bone=skeleton.bones.findIndex(b=>b.name===name);assert(bone>=0,`${piece}: missing ${name}`);
    const ids=[];for(let i=0;i<indices.count;i++)if(indices.getX(i)===bone&&weights.getX(i)>.999999)ids.push(i);
    assert(ids.length>5,`${piece}: unweighted ${name}`);
    return [name,Array.from({length:Math.min(24,ids.length)},(_,i)=>ids[Math.floor(i*ids.length/Math.min(24,ids.length))])];
  }));
  const sample=()=>{gltf.scene.updateMatrixWorld(true);skeleton.update();return Object.fromEntries(Object.entries(groups).map(([name,ids])=>[name,ids.map(i=>mesh.getVertexPosition(i,new Vector3()).applyMatrix4(mesh.matrixWorld))]));};
  const rest=sample(),mixer=new AnimationMixer(gltf.scene),row={piece,tier,joints:skeleton.bones.length,clips:{}};
  for(const clip of gltf.animations){
    mixer.stopAllAction();const action=mixer.clipAction(clip);action.reset().play();action.paused=true;
    const peak=Object.fromEntries(sampleNames.map(n=>[n,0]));let rigidError=0;
    for(let frame=0;frame<=40;frame++){
      action.time=clip.duration*frame/40-.000001;if(frame===0)action.time=0;mixer.update(0);const pose=sample();
      for(const name of sampleNames){
        pose[name].forEach((p,i)=>peak[name]=Math.max(peak[name],p.distanceTo(rest[name][i])));
        if(['Weapon','WheelR','Barrel','ThrowArm'].includes(name))for(let i=1;i<pose[name].length;i++)rigidError=Math.max(rigidError,Math.abs(pose[name][0].distanceTo(pose[name][i])-rest[name][0].distanceTo(rest[name][i])));
      }
    }
    assert(peak.FixedPedestal<1e-5,`${piece}/${tier}/${clip.name}: base drift ${peak.FixedPedestal}`);
    assert(rigidError<1e-5,`${piece}/${tier}/${clip.name}: rigid equipment stretches ${rigidError}`);
    if(clip.name==='walk'&&peak.WheelR!==undefined)assert(peak.WheelR>.12,`${piece}: wheel does not turn`);
    const leg=sampleNames.find(n=>n.includes('Lower'));
    if(leg&&['walk','run'].includes(clip.name))assert(peak[leg]>.025,`${piece}: missing gait`);
    if(clip.name==='attack'){
      if(piece==='cannon_red')assert(peak.Barrel>.075,`${piece}: missing recoil`);
      else if(piece==='cannon_black')assert(peak.ThrowArm>.30,`${piece}: missing throwing arc`);
      else assert(peak.Weapon>.3,`${piece}: missing rider strike`);
    }
    row.clips[clip.name]={maxVertexDisplacement:peak,maxRigidLengthError:rigidError};
  }
  assert.equal(Object.keys(row.clips).length,6);
  if(piece.startsWith('cannon'))assert(gltf.scene.getObjectByName('Muzzle'));
  report.push(row);console.log('ARTICULATION_OK',piece,tier,'joints',row.joints);
}
await mkdir('docs/asset-reports/motion',{recursive:true});
await writeFile('docs/asset-reports/motion/vehicle-articulation.json',JSON.stringify(report,null,2));
