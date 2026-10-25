const {chromium}=require('playwright');const fs=require('fs');
(async()=>{const out=process.argv[2],step=process.argv[3]?+process.argv[3]:null;const b=await chromium.launch();
const p=await b.newPage({viewport:{width:1280,height:720}});const errs=[];p.on('pageerror',e=>errs.push(e.message));
await p.goto('file://'+__dirname+'/scene.html');await p.waitForTimeout(300);
const total=await p.evaluate(()=>T.total);
if(step){const times=process.argv.slice(3).map(Number);for(const t of times){await p.evaluate(t=>render(t),t);await p.screenshot({path:out+'/p'+t+'.png'})}}
else{fs.mkdirSync(out,{recursive:true});const n=Math.round(total*30);for(let i=0;i<n;i++){await p.evaluate(t=>render(t),i/30);await p.screenshot({path:out+'/f'+String(i).padStart(5,'0')+'.jpg',type:'jpeg',quality:92})}}
console.log('errors',errs);await b.close()})();
