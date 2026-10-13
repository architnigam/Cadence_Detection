// Real browser smoke test, synthetic inputs only. Run with the bundled Node runtime.
const fs=require('node:fs'),path=require('node:path');
async function main(){
 const packages=path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
 const {chromium}=require(path.join(packages,'playwright'));
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}), errors=[];
  page.on('pageerror',e=>errors.push(e.name));
  await page.goto(process.env.CADENCE_UI_URL||'http://127.0.0.1:8765',{waitUntil:'networkidle'});
  await page.locator('#file').setInputFiles('data/synthetic/pipeline_inputs/valid.pptx');
  await page.locator('#run').click();
  await page.waitForFunction(()=>document.getElementById('decision').textContent.includes('Checks passed'),null,{timeout:90000});
  if(await page.locator('#download').isDisabled())throw Error('Approved download disabled');
  fs.mkdirSync('tmp/ui-preview',{recursive:true});await page.screenshot({path:'tmp/ui-preview/approved.png',fullPage:true});
  const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#download').click()]);
  const saved='tmp/ui-preview/sanitized.txt';await download.saveAs(saved);
  const text=fs.readFileSync(saved,'utf8');if(text.includes('Noor Example')||text.includes('noor@example.invalid'))throw Error('Known synthetic PII survived');
  await page.locator('#file').setInputFiles('data/synthetic/pipeline_inputs/corrupt.pdf');
  await page.locator('#run').click();
  await page.waitForFunction(()=>document.getElementById('decision').textContent.includes('Review required'),null,{timeout:30000});
  if(!await page.locator('#download').isDisabled())throw Error('Quarantined download enabled');
  await page.screenshot({path:'tmp/ui-preview/quarantined.png',fullPage:true});
  if(errors.length)throw Error('Browser JavaScript error');
  console.log('Browser UI passed: upload, progress, approved download, known-value removal and quarantine export block.');
 }finally{await browser.close()}
}
main().catch(e=>{console.error(e.message);process.exitCode=1});
