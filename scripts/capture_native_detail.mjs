/* global console, process, Event */
import {chromium} from 'playwright';
import {mkdir,readFile} from 'node:fs/promises';
const pieces=(process.argv[2]??'horse_red,soldier_black,general_black,elephant_red').split(',');
const output='.meshy/native-refine/browser';
await mkdir(output,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
  for(const piece of pieces){
    const page=await browser.newPage({viewport:{width:1480,height:1000}});
    if(process.argv.includes('--rest')){
      const manifest=JSON.parse(await readFile(`public/assets/review/production/${piece}/manifest.json`,'utf8'));
      manifest.review_clips=['idle'];
      await page.route(`**/assets/review/native-motion/${piece}/manifest.json`,route=>route.fulfill({json:manifest}));
    }
    await page.goto(`http://127.0.0.1:4175/native-motion-gallery.html?asset=${piece}`);
    await page.locator('#viewport[data-loaded="mobile"]').waitFor({timeout:60000});
    const clips=await page.locator('#clip option').evaluateAll(options=>options.map(o=>o.value));
    for(const clip of clips){
      await page.selectOption('#clip',clip);
      for(const view of ['front','side','detail','base']){
        await page.locator(`[data-view="${view}"]`).click();
        for(const progress of [0,250,500,750]){
          await page.locator('#playhead').evaluate((node,v)=>{node.value=String(v);node.dispatchEvent(new Event('input',{bubbles:true}));},progress);
          await page.waitForTimeout(140);
          await page.locator('#viewport').screenshot({path:`${output}/${piece}-${process.argv.includes('--rest')?'rest':clip}-${view}-${progress}.png`});
        }
      }
    }
    await page.close();console.log('DETAIL_CAPTURED',piece);
  }
}finally{await browser.close();}
