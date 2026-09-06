/* global console, process, Event */
import {chromium} from 'playwright';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {PNG} from 'pngjs';

const output='docs/asset-reports/native-motion/browser';
await mkdir(output,{recursive:true});
const entries=JSON.parse(await readFile('docs/asset-reports/native-motion/staging.json','utf8'));
const selected=process.argv[2]?.split(',');
const browser=await chromium.launch({channel:'chrome',headless:true});
const results=[];
try{
  for(const entry of entries.filter(row=>!selected||selected.includes(row.piece))){
    const page=await browser.newPage({viewport:{width:1280,height:880}});
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
    await page.goto(`http://127.0.0.1:4175/native-motion-gallery.html?asset=${entry.piece}`);
    const viewport=page.locator('#viewport[data-loaded="mobile"]');
    await viewport.waitFor({timeout:60000});
    if(await viewport.getAttribute('data-source-version')!==String(entry.source_version))throw new Error('Stale candidate version: '+entry.piece);
    const options=await page.locator('#clip option').evaluateAll(nodes=>nodes.map(node=>node.value));
    const reviewClips=entry.review_clips??entry.generated_clips;
    if(JSON.stringify(options.slice().sort())!==JSON.stringify(reviewClips.slice().sort()))throw new Error('Incorrect review-clip filter: '+entry.piece);
    const row={piece:entry.piece,sourceVersion:entry.source_version,clips:[],maxBaseDrift:0};
    for(const clip of reviewClips){
      await page.selectOption('#clip',clip);
      const frames=[];
      for(const progress of [100,600]){
        await page.locator('#playhead').evaluate((node,value)=>{node.value=String(value);node.dispatchEvent(new Event('input',{bubbles:true}));},progress);
        await page.waitForTimeout(180);
        const state=await viewport.evaluate(node=>({...node.dataset}));
        if(Number(state.fixedSamples)<1||Number(state.baseDrift)>1e-5)throw new Error('Fixed pedestal failed: '+entry.piece+' '+JSON.stringify(state));
        row.maxBaseDrift=Math.max(row.maxBaseDrift,Number(state.baseDrift));
        frames.push(PNG.sync.read(await viewport.screenshot({path:`${output}/${entry.piece}-${clip}-${progress}.png`})));
      }
      const [a,b]=frames;let changed=0;
      for(let i=0;i<a.data.length;i+=4){if(Math.max(...[0,1,2].map(channel=>Math.abs(a.data[i+channel]-b.data[i+channel])))>10)changed++;}
      if(changed<40)throw new Error('No visible pose change: '+entry.piece+' '+clip+' '+changed);
      row.clips.push({clip,changedPixels:changed});
    }
    if(errors.length)throw new Error(entry.piece+': '+errors.join('\n'));
    await page.screenshot({path:`${output}/${entry.piece}-page.png`});
    await page.selectOption('#sample-version','before');
    await page.waitForURL(/sample=before/);
    await viewport.waitFor({timeout:60000});
    const before=await viewport.getAttribute('data-source-version');
    if(before===String(entry.source_version))throw new Error('Previous candidate did not load: '+entry.piece);
    await page.selectOption('#sample-version','current');
    await page.waitForURL(/sample=current/);
    await viewport.waitFor({timeout:60000});
    if(await viewport.getAttribute('data-source-version')!==String(entry.source_version))throw new Error('Current candidate did not reload: '+entry.piece);
    if(errors.length)throw new Error(entry.piece+': '+errors.join('\n'));
    row.comparisonSwitch=true;
    row.errors=errors;results.push(row);await page.close();
    console.log('NATIVE_BROWSER_QA',entry.piece,JSON.stringify(row.clips));
  }
}finally{
  await browser.close();
  await writeFile(`${output}/results${selected?'-'+selected.join('-'):''}.json`,JSON.stringify(results,null,2));
}
