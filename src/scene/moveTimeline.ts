import { boardToWorld } from '../game/coordinates';
import type { MovePlayback } from '../game/types';

export const CAPTURE = { attack: .55, launch: 1.03, contact: 1.35, death: 1.62, fade: 2.43, gone: 2.91, settle: 2.85, end: 3.43 } as const;
export const clamp = (v:number) => Math.max(0,Math.min(1,v));
export const ease = (v:number) => { const p=clamp(v);return p*p*(3-2*p); };
export function playbackSeconds(move:MovePlayback, now=performance.now()) {
  return Math.max(0,(now-move.startedAt)/1000)/(move.effectLevel==='reduced'?.65:1);
}
export function playbackDuration(move:MovePlayback) {
  return move.effectLevel==='off'?.09:move.captured?CAPTURE.end:.65;
}
export function attackerPosition(move:MovePlayback,t:number):[number,number,number] {
  const from=boardToWorld(move.from),to=boardToWorld(move.to);
  let p:number;
  const y=.25;
  if(move.effectLevel==='off') p=ease(t/.09);
  else if(!move.captured) p=ease(t/.65);
  else {
    const distance=Math.hypot(to[0]-from[0],to[2]-from[2]);
    const approach=move.piece.type==='cannon'?0:Math.max(0,1-.96/distance);
    p=approach*ease(t/CAPTURE.attack)+(1-approach)*ease((t-CAPTURE.settle)/(CAPTURE.end-CAPTURE.settle));
  }
  return [from[0]+(to[0]-from[0])*p,y,from[2]+(to[2]-from[2])*p];
}

export function motionPose(move:MovePlayback|null,id:number,t:number) {
  if(!move || move.effectLevel==='off')return {clip:'idle',progress:0,weight:0};
  if(move.captured?.id===id) {
    if(t<CAPTURE.contact)return {clip:'idle',progress:0,weight:0};
    if(t<CAPTURE.death)return {clip:'hit',progress:clamp((t-CAPTURE.contact)/(CAPTURE.death-CAPTURE.contact))*.65,weight:ease((t-CAPTURE.contact)/.06)};
    return {clip:'death',progress:clamp((t-CAPTURE.death)/(CAPTURE.gone-CAPTURE.death)),weight:1};
  }
  if(move.piece.id!==id)return {clip:'idle',progress:0,weight:0};
  if(!move.captured)return {clip:move.piece.type==='horse'?'run':'walk',progress:clamp(t/.65),weight:Math.min(ease(t/.10),ease((.65-t)/.12))};
  if(t<CAPTURE.attack)return {clip:move.piece.type==='horse'?'run':'walk',progress:clamp(t/CAPTURE.attack),weight:move.piece.type==='cannon'?0:ease(t/.1)};
  if(t<CAPTURE.settle)return {clip:'attack',progress:clamp((t-CAPTURE.attack)/1.35),weight:Math.min(ease((t-CAPTURE.attack)/.10),ease((CAPTURE.settle-t)/.30))};
  return {clip:'walk',progress:clamp((t-CAPTURE.settle)/(CAPTURE.end-CAPTURE.settle)),weight:Math.min(ease((t-CAPTURE.settle)/.08),ease((CAPTURE.end-t)/.12))};
}
