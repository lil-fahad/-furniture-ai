import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import assert from 'node:assert/strict';
import {chromium} from 'playwright';

const directory=await mkdtemp(join(tmpdir(),'furniture-browser-'));
const python=process.env.TEST_PYTHON||'python';
const port=process.env.TEST_BROWSER_PORT||'8765';
const origin=`http://127.0.0.1:${port}`;
const env={...process.env,FURNITURE_ENVIRONMENT:'test',FURNITURE_DATABASE_URL:`sqlite:///${directory}/test.db`,FURNITURE_DATA_DIR:join(directory,'objects'),FURNITURE_PUBLIC_ORIGIN:origin,FURNITURE_ALLOWED_HOSTS:'["127.0.0.1"]'};
const setup=spawnSync(python,['-c',`from furniture_ai.config import Settings
from furniture_ai.db import Base,make_engine,sessions
from furniture_ai.cli import create_user
from PIL import Image
s=Settings(); e=make_engine(s.database_url); Base.metadata.create_all(e)
create_user(sessions(e),'browser-check','Isolated-test-12345','Browser test')
Image.new('RGB',(640,480),'#bdafa0').save('${directory}/room.png')`],{env,encoding:'utf8'});
assert.equal(setup.status,0,setup.stderr);
const server=spawn(python,['-m','uvicorn','furniture_ai.api:app','--host','127.0.0.1','--port',port,'--no-proxy-headers'],{env,stdio:['ignore','ignore','pipe']});
let serverLog='';server.stderr.on('data',chunk=>serverLog+=chunk);
let browser;
try {
  let ready=false;
  for(let i=0;i<60;i++){try{ready=(await fetch(`${origin}/health/live`)).ok;if(ready)break;}catch{}await new Promise(resolve=>setTimeout(resolve,200));}
  assert.ok(ready,serverLog);
  browser=await chromium.launch({headless:true,executablePath:process.env.TEST_CHROME||undefined,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(origin);await page.waitForLoadState('networkidle');
  await page.getByRole('textbox',{name:'Username',exact:true}).fill('browser-check');
  await page.getByLabel('Password',{exact:true}).fill('Isolated-test-12345');
  await page.getByRole('button',{name:'Open studio'}).click();
  await page.locator('#studio').waitFor({state:'visible'});
  await page.locator('#title').fill('Browser test room');
  await page.locator('#image-file').setInputFiles(join(directory,'room.png'));
  await page.locator('#width').fill('5');await page.locator('#length').fill('4');
  await page.locator('#confirmed').check();await page.locator('#analyze').click();
  await page.locator('#job-progress').waitFor({state:'visible'});
  await page.locator('#cancel-job').click();
  await page.getByRole('status').filter({hasText:'Job cancelled.'}).waitFor();
  await mkdir('test-results',{recursive:true});
  await page.screenshot({path:'test-results/studio.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.locator('#mobile-project-select').selectOption('');
  assert.equal(await page.locator('#title').inputValue(),'');
  await page.locator('#mobile-project-select').selectOption({label:'Browser test room'});
  await page.locator('#title').filter({visible:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('#title').value==='Browser test room');
  await page.screenshot({path:'test-results/mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('Browser passed: sign-in, upload, queue, cancel, mobile project reload and no JavaScript errors.');
} finally {
  if(browser)await browser.close();
  server.kill('SIGTERM');
  await new Promise(resolve=>server.once('exit',resolve));
  await rm(directory,{recursive:true,force:true});
}
