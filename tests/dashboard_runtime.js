/* Lightweight DOM interaction smoke test; browser layout verification is separate. */
async function dashboardSmoke(source, data, html, research={schema_version:"1.0",studies:[],reviews:[],monitor:[],neural:[],scenarios:[],review_source:"not_run",unreviewed_samples:0}, widgetsSource="", detailFiles={}) {
  class Element {
    constructor(tag) { this.tagName=tag;this.children=[];this.attributes={};this.listeners={};this.value='';this.textContent='';this.dataset={};this.style={};this.classes=new Set();this.classList={toggle:(name,on)=>{const enabled=on??!this.classes.has(name);enabled?this.classes.add(name):this.classes.delete(name);return enabled;},remove:name=>this.classes.delete(name)}; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children=[...nodes];if(this.tagName==='select')this.value=nodes[0]?.value??''; }
    setAttribute(key,value) { this.attributes[key]=value; }
    addEventListener(kind,handler) { this.listeners[kind]=handler; }
  }
  const ids=new Map([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new Element(['backend','model','topology','condition','run-select','trace-agent','trace-type','neural-select','research-model-filter','research-task-filter','research-size-filter','research-outcome-filter','neuron-layer','neuron-index','monitor-select','interp-model','interp-evidence','interp-effect-metric','interp-monitor-metric'].includes(m[1])?'select':'div')]));
  const document={body:new Element('body'),getElementById:id=>{if(!ids.has(id))throw Error(`Missing target ${id}`);return ids.get(id);},createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)};
  for(const id of ['model','topology','condition','trace-agent','trace-type'])ids.get(id).value='all';
  ids.get('interp-effect-metric').value='delta';ids.get('interp-monitor-metric').value='false_positive_rate';
  ids.get('research-outcome-filter').value='all';ids.get('backend').value='live';ids.get('round').value='0';
  class Option extends Element { constructor(text,value){super('option');this.textContent=text;this.value=value;} }
  const widgets=widgetsSource?new Function('document',widgetsSource+'\nreturn EvidenceWidgets;')(document):null;
  const fetched=[];
  const api=new Function('document','Option','fetch','setInterval','EvidenceWidgets',source+'\nreturn {load,render,renderRound,renderTraces,showView,state,loadResearch,researchState,loadStudyDetail};')(document,Option,async url=>(fetched.push(url),{ok:!url.startsWith('data/studies/')||Boolean(detailFiles[url]),json:async()=>url.startsWith('data/research.json')?research:detailFiles[url]??data}),()=>0,widgets);
  await api.load();await api.loadResearch();
  fetched.length=0;await ids.get('refresh').listeners.click();
  if(!fetched.some(u=>u.startsWith('data/results.json'))||!fetched.some(u=>u.startsWith('data/research.json')))throw Error('Refresh must fetch both snapshots');
  if(!ids.get('research-updated').textContent.includes('run attempts'))throw Error('Research freshness missing');
  const comparisonCards=ids.get('comparison').children;
  if(!comparisonCards.length)throw Error('Model comparison cards missing');
  const comparisonDetail=comparisonCards[0].children.find(n=>n.tagName==='details');
  if(!comparisonDetail||comparisonDetail.open||comparisonDetail.children[1].children.length)throw Error('Comparison details must start collapsed and lazy');
  comparisonDetail.open=true;comparisonDetail.listeners.toggle();
  if(!comparisonDetail.children[1].children[0]?.children[1]?.children.length)throw Error('Expanded cohort rows missing');
  let detailedConditions=0;
  for(const card of comparisonCards){const detail=card.children.find(n=>n.tagName==='details');detail.open=true;detail.listeners.toggle();detailedConditions+=detail.children[1].children[0].children[1].children.length;if(detail!==comparisonDetail){detail.open=false;detail.listeners.toggle();}}
  if(detailedConditions!==new Set(api.state.runs.map(r=>[r.cohort,r.topology,r.intervention].join('|'))).size)throw Error('Visual cards lost or pooled cohort conditions');

  api.render();
  if(!ids.get('comparison').children[0].children.find(n=>n.tagName==='details')?.open)throw Error('Expanded comparison lost on refresh');
  ids.get('comparison-search').value='__no_matching_model__';ids.get('comparison-search').listeners.input();
  if(!ids.get('comparison-count').textContent.startsWith('0 model'))throw Error('Comparison search did not filter');
  ids.get('comparison-search').value='';ids.get('comparison-search').listeners.input();

  if(ids.get('interp-kpis').children.length!==6)throw Error('Interpretability headline metrics missing');
  if(research.neural.length&&!ids.get('interp-capture-grid').children.length)throw Error('Visible capture cards missing');
  if(!ids.get('interp-effects').children.length)throw Error('Interpretability overview chart missing');
  const captureCards=ids.get('interp-capture-grid').children;
  if(captureCards.length){const card=captureCards[Math.min(1,captureCards.length-1)],button=card.children.find(n=>n.tagName==='button'),details=card.children.find(n=>n.tagName==='details');if(!button||!details)throw Error('Capture card navigation missing');button.listeners.click();details.open=true;details.listeners.toggle();if(!details.children.find(n=>n.tagName==='div')?.children.length)throw Error('Inline activation profile missing');}

  if(!ids.get("neural-evidence").children.length)throw Error("Missing honest neural empty state");
  if(api.researchState.snapshot.scenarios.length!==research.scenarios.length)throw Error("Scenario catalog missing");
  const detailRow=research.studies.find(r=>detailFiles[r.detail_file]);
  if(detailRow){await api.loadStudyDetail(detailRow);if(!ids.get('study-detail').children.some(n=>n.textContent==='Assigned task'))throw Error('Task drill-down missing');}
  if(!api.state.runs.length)throw Error('No initial runs rendered');
  const expected=(data.runs.filter(r=>ids.get('backend').value==='mock'?r.backend==='mock':r.backend!=='mock').length)+(research.studies.filter(r=>ids.get('backend').value==='mock'?r.backend==='mock':r.backend!=='mock').length);
  if(api.state.runs.length!==expected)throw Error('Main overview omitted newer study runs');
  if(ids.get('runs-kpi').textContent!==`${api.state.runs.filter(r=>r.status==='completed').length} / ${expected}`)throw Error('Main run counter is stale');
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
  dashboardSmoke(fs.readFileSync(path.join(root,'app.js'),'utf8'),JSON.parse(fs.readFileSync(path.join(root,'data/results.json'),'utf8')),fs.readFileSync(path.join(root,'index.html'),'utf8'),JSON.parse(fs.readFileSync(path.join(root,'data/research.json'),'utf8')),fs.readFileSync(path.join(root,'widgets.js'),'utf8'),Object.fromEntries(fs.existsSync(path.join(root,'data/studies'))?fs.readdirSync(path.join(root,'data/studies')).filter(n=>n.endsWith('.json')).map(n=>['data/studies/'+n,JSON.parse(fs.readFileSync(path.join(root,'data/studies',n),'utf8'))]):[])).then(console.log).catch(error=>{console.error(error);process.exitCode=1;});
}
