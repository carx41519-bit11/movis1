const {chromium}=require('playwright');
const fs=require('fs'),assert=require('assert');
(async()=>{
 const f=JSON.parse(fs.readFileSync('.work/browser-fixture.json','utf8'));
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8097');
 await page.locator('#username').fill(f.username);await page.locator('#password').fill(f.password);await page.locator('#login-form button').click();
 await page.locator('#app').waitFor({state:'visible'});
 await page.locator('#content').getByText('Sinandomeng',{exact:true}).waitFor();
 async function call(path,data,token){const r=await context.request.post('http://127.0.0.1:8097'+path,{data,headers:{Origin:'http://127.0.0.1:8097',...(token?{Authorization:'Bearer '+token}:{})}});assert(r.ok(),await r.text());return r.json();}
 const login=await call('/login',{username:f.staff,password:f.password});const token=login.token;
 const img=''/****/;
 const pixels=fs.readFileSync('.work/test-image.jpg').toString('base64');
 const req=d=>({request_id:require('crypto').randomUUID(),...d});
 async function action(kind,quantity){const a=await call('/v2/open',req({kind,products:[1]}),token);const iid=require('crypto').randomUUID();await call('/v2/image',{action_id:a.action_id,image_id:iid,source:'camera',zoom:1,image:pixels},token);let s=await (await context.request.get('http://127.0.0.1:8097/v2/state?action_id='+a.action_id,{headers:{Authorization:'Bearer '+token}})).json();await call('/v2/review',req({action_id:a.action_id,image_id:iid,revision:s.action.revision,checked:[{product_id:1,quantity}],confirmed:true}),token);s=await (await context.request.get('http://127.0.0.1:8097/v2/state?action_id='+a.action_id,{headers:{Authorization:'Bearer '+token}})).json();return {id:a.action_id,revision:s.action.revision};}
 const incoming=await action('stock-in',20);await call('/v2/submit',req({action_id:incoming.id,revision:incoming.revision,reason:'Browser receiving check',unique_sacks:true}),token);
 const ret=await action('return',3);await call('/v2/submit',req({action_id:ret.id,revision:ret.revision,reason:'Customer return',condition:'Unopened usable sacks',already_stocked:false,unique_sacks:true}),token);
 const count=await action('count',18);await call('/v2/finish',req({action_id:count.id,revision:count.revision,reason:'Full physical count',unique_sacks:true,full_counts:{'1':true}}),token);
 await page.locator('#refresh').click();await page.waitForTimeout(200);
 await page.screenshot({path:'.work/web-overview.png',fullPage:true});
 await page.getByRole('button',{name:'Scans and counts',exact:true}).click();
 await page.locator('[data-action="'+count.id+'"]').click();await page.locator('#adjust').waitFor();
 await page.locator('#adjust input[name=reason]').fill('Owner verified full count');await page.locator('#adjust button').click();await page.locator('#detail').waitFor({state:'hidden'});
 await page.getByRole('button',{name:'Returns and damage',exact:true}).click();await page.getByRole('button',{name:'Inspect and decide',exact:true}).click();
 await page.locator('#decision input[name=reason]').fill('Owner inspected and approved');await page.locator('#decision input[name=inspected]').check();await page.locator('#decision input[name=usable]').check();await page.locator('#decision button').click();await page.locator('#detail').waitFor({state:'hidden'});
 await page.getByRole('button',{name:'Rice products',exact:true}).click();await page.locator('#search').fill('Sinandomeng');await page.getByRole('button',{name:'Edit details'}).click();await page.locator('#product input[name=description]').fill('Sinandomeng rice in 25 kg sacks');await page.locator('#product button').click();await page.locator('#detail').waitFor({state:'hidden'});
 await page.getByRole('button',{name:'Accounts',exact:true}).click();await page.locator('[data-user="2"]').click();await page.locator('#access input[name=can_adjust]').check();await page.locator('#access button').click();await page.locator('#detail').waitFor({state:'hidden'});
 await page.getByRole('button',{name:'Stock history',exact:true}).click();const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export CSV'}).click();assert((await download).suggestedFilename().endsWith('.csv'));
 const shared=await (await context.request.get('http://127.0.0.1:8097/v2/state',{headers:{Authorization:'Bearer '+token}})).json();assert.equal(shared.products[0].quantity,21);assert(shared.user.can_adjust);
 await page.getByRole('button',{name:'Scans and counts',exact:true}).click();await page.locator('[data-action="'+ret.id+'"]').click();await page.locator('#detail img').waitFor();await page.screenshot({path:'.work/web-review.png',fullPage:true});await page.locator('#close-detail').click();
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Overview',exact:true}).click();await page.screenshot({path:'.work/web-mobile.png',fullPage:true});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
 console.log('Browser PASS: admin login, shared staff API, count correction, return approval, product edit, permissions, CSV, raw scan review, mobile layout; stock=21');
 await browser.close();
})().catch(e=>{console.error(e.message);process.exit(1);});
