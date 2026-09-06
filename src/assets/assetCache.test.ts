import { describe, expect, it, vi } from "vitest";
import { AssetCache } from "./assetCache";
import { choosePieceTier } from "./quality";

describe("shared runtime asset lifecycle",()=>{
  it("shares one request, isolates a failure, and retries only the failed asset",async()=>{
    const calls:string[]=[];let repaired=false;
    const cache=new AssetCache(async key=>{calls.push(key);if(key==='bad'&&!repaired)throw new Error('404');return {value:key,fallback:key==='fallback'};},()=>{},2,5);
    const release=[cache.subscribe('shared',()=>{}),cache.subscribe('shared',()=>{}),cache.subscribe('bad',()=>{}),cache.subscribe('fallback',()=>{})];
    await vi.waitFor(()=>expect(cache.stats().loading).toBe(0));
    expect(calls.filter(k=>k==='shared')).toHaveLength(1);expect(cache.snapshot('shared').status).toBe('ready');expect(cache.snapshot('bad').status).toBe('failed');
    expect(cache.snapshot('fallback').fallback).toBe(true);repaired=true;cache.retryFailures();
    await vi.waitFor(()=>expect(cache.snapshot('bad').status).toBe('ready'));
    expect(calls).toEqual(['shared','bad','fallback','bad']);release.forEach(fn=>fn());
  });
  it("keeps a shared resource alive until its last instance is released",async()=>{
    const dispose=vi.fn();const cache=new AssetCache(async()=>({value:{model:'same'}}),dispose,1,5);
    const a=cache.subscribe('piece',()=>{}),b=cache.subscribe('piece',()=>{});
    await vi.waitFor(()=>expect(cache.snapshot('piece').status).toBe('ready'));
    a();await new Promise(resolve=>setTimeout(resolve,10));expect(dispose).not.toHaveBeenCalled();
    b();await vi.waitFor(()=>expect(dispose).toHaveBeenCalledTimes(1));
  });
  it("limits concurrent decodes",async()=>{
    let active=0,maximum=0;
    const cache=new AssetCache(async key=>{active++;maximum=Math.max(maximum,active);await new Promise(resolve=>setTimeout(resolve,8));active--;return {value:key};},()=>{},2,5);
    const release=['a','b','c','d','e'].map(key=>cache.subscribe(key,()=>{}));
    await vi.waitFor(()=>expect(cache.stats().ready).toBe(5));expect(maximum).toBe(2);release.forEach(fn=>fn());
  });
});
describe("piece quality selection",()=>{
  it("keeps mobile within 2K and avoids oscillation near a size boundary",()=>{
    expect(choosePieceTier(300,true,'high',true,'distant')).toBe('mobile');
    expect(choosePieceTier(100,false,'auto',false,'distant')).toBe('distant');
    expect(choosePieceTier(100,false,'auto',false,'mobile')).toBe('mobile');
    expect(choosePieceTier(200,true,'auto',false,'mobile')).toBe('desktop');
    expect(choosePieceTier(500,true,'low',false,'desktop')).toBe('distant');
  });
});
