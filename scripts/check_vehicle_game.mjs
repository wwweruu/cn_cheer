/* global console,window */
import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const out='docs/asset-reports/motion/vehicles';await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000},recordVideo:{dir:out+'/video',size:{width:1152,height:800}}});
const page=await context.newPage(),report={moves:[],captures:[]},errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
  await page.goto('http://127.0.0.1:4175/?audit=1');
  await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__?.pieces.length===32&&window.__CHESS_DIAGNOSTICS__.pieces.every(p=>p.status==='ready'),{}, {timeout:90000});
  await page.getByLabel('切换顶视').click();await page.waitForTimeout(1700);
  const click=async(f,r)=>{
    const p=await page.evaluate(([f,r])=>window.__CHESS_DIAGNOSTICS__.points.find(p=>p.file===f&&p.rank===r),[f,r]);
    const box=await page.locator('canvas').boundingBox();await page.mouse.click(box.x+p.x,box.y+p.y);
  };
  const begin=async(f,r,tf,tr)=>{await click(f,r);await page.waitForTimeout(150);await click(tf,tr);};
  const restart=async()=>{
    await page.getByLabel('重新开局',{exact:true}).click();
    const dialog=page.getByRole('alertdialog');
    if(await dialog.isVisible())await dialog.getByRole('button',{name:'重新开局',exact:true}).click();
    await page.waitForTimeout(350);
  };
  for(const [asset,from,to,clip] of [
    ['horse_red',[1,9],[2,7],'run'],['horse_black',[1,0],[2,2],'run'],
    ['chariot_red',[0,9],[0,7],'walk'],['chariot_black',[0,0],[0,2],'walk']]){
    await begin(...from,...to);
    await page.waitForFunction(([asset,clip])=>window.__CHESS_DIAGNOSTICS__.pieces.some(p=>p.asset===asset&&p.motion.clip===clip),[asset,clip],{timeout:2200});
    const state=await page.evaluate(([asset,clip])=>window.__CHESS_DIAGNOSTICS__.pieces.find(p=>p.asset===asset&&p.motion.clip===clip),[asset,clip]);
    assert.equal(state.position[1],.25);report.moves.push({asset,...state});
    await page.screenshot({path:`${out}/${asset}-moving.png`});await page.waitForTimeout(750);
  }
  for(const camp of ['red','black']){
    await restart();
    if(camp==='black'){await begin(0,6,0,5);await page.waitForTimeout(850);}
    const from=camp==='red'?[1,7]:[1,2],to=camp==='red'?[1,0]:[1,9];
    await begin(...from,...to);
    await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__.projectile?.visible,{}, {timeout:2800});
    const snapshot=await page.evaluate(()=>window.__CHESS_DIAGNOSTICS__);
    const attacker=snapshot.pieces.find(p=>p.asset===`cannon_${camp}`&&p.motion.clip==='attack');
    assert(attacker);assert(snapshot.projectile.launchOrigin?.length===3);assert(attacker.muzzle?.length===3);
    const launch=snapshot.projectile.launchOrigin,origin=attacker.position;
    const direction=camp==='red'?-1:1;
    assert((launch[2]-origin[2])*direction>.1,'Projectile must start in front of the aimed weapon');
    assert(launch[1]>.95,'Projectile must originate at the animated muzzle');
    report.captures.push({camp,attacker,projectile:snapshot.projectile});
    await page.screenshot({path:`${out}/cannon_${camp}-firing.png`});
    await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__.pieces.length===31,{}, {timeout:5000});
    await page.getByLabel('悔棋').click();await page.waitForFunction(()=>window.__CHESS_DIAGNOSTICS__.pieces.length===32);
  }
  report.errors=errors;assert.equal(errors.length,0);console.log('VEHICLE_GAME_OK',JSON.stringify({moves:report.moves.map(m=>m.asset),captures:report.captures.map(c=>({camp:c.camp,origin:c.projectile.launchOrigin})),errors}));
}finally{await writeFile(`${out}/game.json`,JSON.stringify(report,null,2));await context.close();await browser.close();}
