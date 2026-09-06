import {describe,it,expect} from 'vitest';
import {attackerPosition,CAPTURE,motionPose,playbackDuration,playbackSeconds} from './moveTimeline';
import {boardToWorld} from '../game/coordinates';
import type {MovePlayback} from '../game/types';
const capture:MovePlayback={id:1,token:7,startedAt:1000,effectLevel:'full',from:{file:4,rank:5},to:{file:4,rank:4},
  piece:{id:1,type:'soldier',camp:'red',position:{file:4,rank:5}},captured:{id:2,type:'soldier',camp:'black',position:{file:4,rank:4}},givesCheck:false,winner:null};
describe('capture choreography',()=>{
  it.each(['soldier','horse'] as const)('holds the %s base on the board and clear of the defender until the fade',type=>{
    const move={...capture,piece:{...capture.piece,type}};
    const target=boardToWorld(move.to);
    for(let t=0;t<CAPTURE.fade;t+=.025){const p=attackerPosition(move,t);expect(Math.hypot(p[0]-target[0],p[2]-target[2])).toBeGreaterThanOrEqual(.959);expect(p[1]).toBe(.25);}
    const end=attackerPosition(move,CAPTURE.end);expect(end[0]).toBe(target[0]);expect(end[2]).toBe(target[2]);
    expect(motionPose(move,2,CAPTURE.contact-.01).clip).toBe('idle');
    expect(motionPose(move,2,CAPTURE.contact+.01).clip).toBe('hit');expect(motionPose(move,2,CAPTURE.death+.01).clip).toBe('death');
  });
  it('fires cannon from its starting square and moves only after the defender fades',()=>{
    const shot={...capture,piece:{...capture.piece,type:'cannon' as const},from:{file:4,rank:8}};
    const from=boardToWorld(shot.from);for(let t=0;t<CAPTURE.settle;t+=.1){expect(attackerPosition(shot,t)).toEqual([from[0],.25,from[2]]);}
  });
  it('uses a shared clock across LOD changes and provides short reduced/off playback',()=>{
    expect(playbackSeconds(capture,1000+CAPTURE.contact*1000)).toBeCloseTo(CAPTURE.contact);
    expect(playbackSeconds({...capture,effectLevel:'reduced'},1000+CAPTURE.contact*650)).toBeCloseTo(CAPTURE.contact);
    expect(playbackDuration({...capture,effectLevel:'off'})).toBe(.09);
    expect(attackerPosition({...capture,effectLevel:'off'},.1)[2]).toBe(boardToWorld(capture.to)[2]);
  });
});
