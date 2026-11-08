/* Lightweight DOM interaction smoke test; browser layout verification is separate. */
async function dashboardSmoke(source, data, html, research={schema_version:"1.0",studies:[],reviews:[],monitor:[],neural:[],scenarios:[],review_source:"not_run",unreviewed_samples:0}) {
  class Element {
    constructor(tag) { this.tagName=tag;this.children=[];this.attributes={};this.listeners={};this.value='';this.textContent='';this.dataset={};this.style={};this.classes=new Set();this.classList={toggle:(name,on)=>{const enabled=on??!this.classes.has(name);enabled?this.classes.add(name):this.classes.delete(name);return enabled;},remove:name=>this.classes.delete(name)}; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children=[...nodes];if(this.tagName==='select')this.value=nodes[0]?.value??''; }
    setAttribute(key,value) { this.attributes[key]=value; }
    addEventListener(kind,handler) { this.listeners[kind]=handler; }
  }
  const ids=new Map([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new Element(['backend','model','topology','condition','run-select','trace-agent','trace-type'].includes(m[1])?'select':'div')]));
  const document={body:new Element('body'),getElementById:id=>{if(!ids.has(id))throw Error(`Missing target ${id}`);return ids.get(id);},createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)};
  for(const id of ['model','topology','condition','trace-agent','trace-type'])ids.get(id).value='all';
  ids.get('backend').value='live';ids.get('round').value='0';
  class Option extends Element { constructor(text,value){super('option');this.textContent=text;this.value=value;} }
  const api=new Function('document','Option','fetch','setInterval',source+'\nreturn {load,render,renderRound,renderTraces,showView,state,loadResearch,researchState};')(document,Option,async url=>({ok:true,json:async()=>url.startsWith('data/research.json')?research:data}),()=>0);
  await api.load();await api.loadResearch();
  if(!ids.get("neural-evidence").children.length)throw Error("Missing honest neural empty state");
  if(api.researchState.snapshot.scenarios.length!==research.scenarios.length)throw Error("Scenario catalog missing");
  if(!api.state.runs.length)throw Error('No initial runs rendered');
  for(const view of ['models','evaluations','traces','datasets','methods','research','neural','overview']){
    api.showView(view);
    if(document.body.dataset.view!==view)throw Error('Navigation failed: '+view);
    if(!ids.get('nav-'+view).classes.has('active'))throw Error('Active navigation failed');
  }
  if(!ids.get('activity-chart').children.length)throw Error('Run activity chart missing');
  if(!ids.get('distribution').children.length)throw Error('Artifact distribution missing');
  if(!ids.get('datasets').children.length)throw Error('Cohort dataset table missing');
  if(!ids.get('quality-bars').children.length)throw Error('Selected-run quality missing');
  if(ids.get('tokens-kpi').textContent==='—')throw Error('Token telemetry not rendered');
  if(!ids.get('network').children.length)throw Error('Missing network');
  ids.get('round').value='1';api.renderRound();
  ids.get('trace-type').value='artifact';api.renderTraces();
  if(data.traces_included&&!ids.get('trace-list').children.length)throw Error('Missing trace content');
  ids.get('condition').value='benign_override';api.render();
  if(api.state.runs.some(r=>r.intervention!=='benign_override'))throw Error('Condition filter failed');
  ids.get('backend').value='mock';api.render();
  if(api.state.runs.some(r=>r.backend!=='mock'))throw Error('Mock isolation failed');
  ids.get('model').value='missing-model';api.render();
  ids.get('backend').value='all';ids.get('condition').value='all';api.render();
  if(!ids.get('comparison').children.length)throw Error('Comparison table missing');
  const base=api.state.runs[0];
  api.state.snapshot={...data,runs:[
    {...base,id:'fixture-a',cohort:'fixture-a',downstream_adoption_rate:0,generated_tokens:null,median_call_seconds:null},
    {...base,id:'fixture-b',cohort:'fixture-b',downstream_adoption_rate:1,generated_tokens:null,median_call_seconds:null}
  ]};api.render();
  if(ids.get('adoption-kpi').textContent!=='0–100%')throw Error('Cohort range was pooled or misrepresented');
  if(ids.get('tokens-kpi').textContent!=='N/A'||ids.get('latency-kpi').textContent!=='N/A')throw Error('Missing telemetry was fabricated');
  ids.get('nav-toggle').listeners.click();
  if(!document.body.classes.has('sidebar-open'))throw Error('Mobile navigation did not open');
  api.showView('traces');
  if(document.body.classes.has('sidebar-open'))throw Error('Mobile navigation did not close');
  api.state.snapshot={...data,runs:[]};api.render();
  if(!ids.get('comparison').children.length)throw Error('Missing empty-state explanation');
  return 'Dashboard JS runtime smoke passed: eight views, metrics, charts, cohort isolation, round replay, traces, and empty states.';
}
if(typeof module!=='undefined'&&require.main===module){
  const fs=require('node:fs'),path=require('node:path'),root=path.join(__dirname,'..','dashboard');
  dashboardSmoke(fs.readFileSync(path.join(root,'app.js'),'utf8'),JSON.parse(fs.readFileSync(path.join(root,'data/results.json'),'utf8')),fs.readFileSync(path.join(root,'index.html'),'utf8'),JSON.parse(fs.readFileSync(path.join(root,'data/research.json'),'utf8'))).then(console.log).catch(error=>{console.error(error);process.exitCode=1;});
}
