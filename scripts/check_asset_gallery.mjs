/* global console,document */
import {chromium} from 'playwright';import {mkdir,writeFile} from 'node:fs/promises';
const ids=['general_red','general_black','advisor_red','advisor_black','elephant_red','elephant_black','horse_red','horse_black','chariot_red','chariot_black','cannon_red','cannon_black','soldier_red','soldier_black'];
const out='docs/asset-reports/pieces';await mkdir(out,{recursive:true});const browser=await chromium.launch({channel:'chrome',headless:true});const reports=[];
try{for(const asset of ids){const page=await browser.newPage({viewport:{width:1200,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:4175/asset-gallery.html?asset='+asset);await page.waitForFunction(()=>document.querySelector('#viewport')?.dataset.loaded==='desktop',{}, {timeout:60000});
 for(const tier of ['desktop','mobile','lod2']) {await page.locator('#quality').selectOption(tier);await page.waitForFunction(t=>document.querySelector('#viewport')?.dataset.loaded===t,tier,{timeout:60000});await page.waitForTimeout(200);await page.locator('#viewport').screenshot({path:`${out}/${asset}-${tier}.png`});reports.push({asset,tier,triangles:await page.locator('#triangles').innerText(),compressed:await page.locator('#viewport').getAttribute('data-compressed-textures'),errors});}
 console.log('GALLERY_QA',asset);await page.close();}
}finally{await browser.close();await writeFile(out+'/browser.json',JSON.stringify(reports,null,2));}
