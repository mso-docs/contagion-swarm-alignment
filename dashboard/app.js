'use strict';
const $ = id => document.getElementById(id);
const state = {snapshot:null, runs:[], selected:null};
const NS = 'http://www.w3.org/2000/svg';
const pct = value => value == null ? 'N/A' : `${(100 * value).toFixed(1)}%`;
const secs = value => value == null ? 'N/A' : value < 60 ? `${value.toFixed(1)}s` : `${(value/60).toFixed(1)}m`;
const mean = xs => { const values=xs.filter(x=>x!=null);return values.length?values.reduce((a,b)=>a+b,0)/values.length:null; };
const median = xs => {const sorted=xs.filter(x=>x!=null).sort((a,b)=>a-b);return sorted.length?(sorted[Math.floor((sorted.length-1)/2)]+sorted[Math.floor(sorted.length/2)])/2:null;};
function el(tag,text,cls){const node=document.createElement(tag);if(text!=null)node.textContent=String(text);if(cls)node.className=cls;return node;}
function svg(tag,attrs={},text){const node=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>node.setAttribute(k,String(v)));if(text!=null)node.textContent=String(text);return node;}
function empty(target,text){target.replaceChildren(el('p',text,'empty'));}
function options(target,values,allLabel){const previous=target.value;target.replaceChildren(new Option(allLabel,'all'),...values.map(v=>new Option(v,v)));target.value=values.includes(previous)?previous:'all';}
function cohortLabel(run){return `${run.backend} · v${run.protocol_version} · ${run.thinking} thinking · ${run.cohort}`;}
function filtered(){return state.snapshot.runs.filter(r=>($('backend').value==='all'||($('backend').value==='mock'?r.backend==='mock':r.backend!=='mock'))&&($('model').value==='all'||r.model===$('model').value)&&($('topology').value==='all'||r.topology===$('topology').value)&&($('condition').value==='all'||r.intervention===$('condition').value));}
function render(){
 const models=state.snapshot.runs.filter(r=>$('backend').value==='all'||($('backend').value==='mock'?r.backend==='mock':r.backend!=='mock')).map(r=>r.model);
 options($('model'),[...new Set(models)].sort(),'All models');
 state.runs=filtered();const complete=state.runs.filter(r=>r.status==='completed');
 $('runs-kpi').textContent=`${complete.length} / ${state.runs.length}`;
 const cohorts=new Set(complete.map(r=>r.cohort));
 $('runs-sub').textContent=`${state.runs.length-complete.length} failed/exhausted · ${cohorts.size} cohort(s)`;
 // Avoid a misleading aggregate across different models, protocols, and sampling settings.
 $('adoption-kpi').textContent=cohorts.size>1?'By cohort':pct(mean(complete.map(r=>r.downstream_adoption_rate)));
 $('boundary-kpi').textContent=cohorts.size>1?'By cohort':pct(mean(complete.map(r=>r.downstream_clean_rate)));
 $('runtime-kpi').textContent=secs(median(state.runs.map(r=>r.duration_seconds)));
 const note=$('dataset-note');const hasMock=state.runs.some(r=>r.backend==='mock');note.classList.toggle('mock',hasMock);
 note.textContent=!state.runs.length?'No runs match these filters. Select mock validation to inspect the software demonstration.':hasMock?'MOCK DATA PRESENT — scripted software validation. It provides no empirical evidence about LLM alignment. Cohorts remain separate below.':'LIVE INFERENCE — exploratory behavioral evidence. Inspect clean controls, failures and exposure before drawing conclusions.';
 renderTable();renderPlots();
 const previous=$('run-select').value;$('run-select').replaceChildren(...state.runs.map(r=>new Option(`${r.model} · ${r.topology} · ${r.intervention==='none'?'control':'injected'} · seed ${r.seed} · ${r.status} · ${r.id.slice(0,6)}`,r.id)));
 if(state.runs.some(r=>r.id===previous))$('run-select').value=previous;
 selectRun();renderObservability();
}
function groups(runs,key){const result=new Map();runs.forEach(r=>{const k=key(r);if(!result.has(k))result.set(k,[]);result.get(k).push(r);});return [...result.values()];}
function renderTable(){const body=$('comparison');body.replaceChildren();
 for(const group of groups(state.runs,r=>[r.cohort,r.topology,r.intervention].join('|'))){const run=group[0],done=group.filter(r=>r.status==='completed'),row=el('tr');
 const model=el('td',run.model);model.append(el('span',run.backend.toUpperCase(),`badge ${run.backend==='mock'?'mock':''}`),el('small',cohortLabel(run)));row.append(model);
 [run.topology+' / '+(run.intervention==='none'?'control':'injected'),`${done.length} / ${group.length}`,pct(mean(done.map(r=>r.downstream_adoption_rate))),pct(mean(done.map(r=>r.downstream_clean_rate))),pct(mean(done.map(r=>r.legitimate_task_success_rate))),secs(median(group.map(r=>r.duration_seconds))),secs(median(group.map(r=>r.median_call_seconds))),mean(done.map(r=>r.messages_delivered))?.toFixed(0)??'N/A'].forEach(v=>row.append(el('td',v)));body.append(row);
 }if(!state.runs.length){const row=el('tr'),cell=el('td','No matching runs.');cell.colSpan=9;row.append(cell);body.append(row);}
}
function renderPlots(){
 const target=$('adoption-chart');target.replaceChildren();const grouped=groups(state.runs.filter(r=>r.status==='completed'),r=>[r.cohort,r.topology,r.intervention].join('|'));
 if(!grouped.length)empty(target,'No completed runs in this selection.');else{
 const width=Math.max(500,grouped.length*115),height=270,plot=svg('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':'Run-level downstream adoption by cohort, network and condition'});
 [0,.25,.5,.75,1].forEach(v=>{const y=190-v*160;plot.append(svg('line',{x1:42,y1:y,x2:width-15,y2:y,class:'gridline'}),svg('text',{x:4,y:y+4,class:'axis-label'},`${v*100}%`));});
 grouped.forEach((g,i)=>{const x=65+(i+.5)*(width-90)/grouped.length;g.forEach((r,j)=>{const dot=svg('circle',{cx:x+(j-(g.length-1)/2)*7,cy:190-r.downstream_adoption_rate*160,r:4,class:`chart-dot ${r.intervention!=='none'?'injected':''}`});dot.append(svg('title',{},`${r.model} / ${r.cohort} / seed ${r.seed}: ${pct(r.downstream_adoption_rate)}`));plot.append(dot);});[g[0].model,g[0].topology+' / '+(g[0].intervention==='none'?'control':'injected'),g[0].cohort.slice(0,6)].forEach((text,j)=>plot.append(svg('text',{x,y:211+j*15,'text-anchor':'middle',class:'axis-label'},text)));});target.append(plot);}
 const runtime=$('runtime-chart');runtime.replaceChildren();const runtimeGroups=groups(state.runs,r=>r.cohort);if(!runtimeGroups.length){empty(runtime,'No attempts in this selection.');return;}
 const width=600,height=Math.max(260,runtimeGroups.length*65+25),plot=svg('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':'Median wall-clock run time by model cohort'});const max=Math.max(...state.runs.map(r=>r.duration_seconds),.001);
 runtimeGroups.forEach((g,i)=>{const y=25+i*65;plot.append(svg('text',{x:0,y,class:'axis-label'},`${g[0].model} / ${g[0].cohort.slice(0,6)}`));const value=median(g.map(r=>r.duration_seconds));plot.append(svg('rect',{x:0,y:y+9,width:Math.max(1,value/max*510),height:15,fill:g[0].backend==='mock'?'#d5a04a':'#409cff',rx:2}),svg('text',{x:Math.min(515,value/max*510+6),y:y+21,class:'axis-label'},secs(value)));});runtime.append(plot);
}
function selectRun(){state.selected=state.runs.find(r=>r.id===$('run-select').value)||null;const run=state.selected;$('run-meta').replaceChildren();if(!run){['network','agents','trajectory','run-details','trace-list'].forEach(id=>empty($(id),'Select a run to inspect its evidence.'));renderRunQuality();return;}
 [run.status,run.backend.toUpperCase(),`protocol ${run.protocol_version}`,`seed ${run.seed}`,`thinking ${run.thinking}`,`cohort ${run.cohort}`].forEach(text=>$('run-meta').append(el('span',text,'meta-chip')));
 $('round').max=String(run.rounds-1);$('round').value=String(Math.min(Number($('round').value),run.rounds-1));
 $('run-details').replaceChildren();const details={Model:run.model,Digest:run.model_digest??'Not supplied',Runtime:secs(run.duration_seconds),'Calls returned / invoked':`${run.completed_calls} / ${run.attempted_calls}`,'HTTP attempts':run.http_attempts,'Parse failures':run.parse_failures,'Generated tokens':run.generated_tokens??'Not recorded','Generation tokens/s':run.generation_tokens_per_second?.toFixed(1)??'Not recorded','First adoption delay':run.first_downstream_adoption==null?'None observed':`${run.first_downstream_adoption} round(s)`,'Maximum distance':run.maximum_propagation_distance??'N/A','Config sampling':`temperature ${run.temperature} / ${run.max_output_tokens} tokens`,'Started UTC':run.started_utc,'Source hash':run.source_hash};Object.entries(details).forEach(([key,value])=>$('run-details').append(el('dt',key),el('dd',value)));
 renderRound();renderRunQuality();
}
function agentState(agent){if(!agent)return'waiting';if(agent.adopted_instruction)return'adopted';if(agent.legitimate_task_success)return'clean';if(agent.exposed)return'exposed';return'waiting';}
function renderRound(){const run=state.selected;if(!run)return;const round=Number($('round').value);$('round-label').textContent=String(round);const observed=[...run.timeline].reverse().find(t=>t.round<=round);const agentMap=new Map((observed?.agents??[]).map(a=>[a.agent_id,a]));
 const graph=svg('svg',{viewBox:'0 0 480 300',role:'img','aria-label':`${run.topology} network at round ${round}`});const coords={};Object.keys(run.graph).forEach((id,i)=>{const angle=-Math.PI/2+i*2*Math.PI/5;coords[id]=run.topology==='star'?(i===0?[240,145]:[240+120*Math.cos((i-1)*Math.PI/2),145+100*Math.sin((i-1)*Math.PI/2)]):[240+145*Math.cos(angle),145+112*Math.sin(angle)];});
 Object.entries(run.graph).forEach(([sender,neighbors])=>neighbors.forEach(receiver=>{if(sender<receiver){const [x1,y1]=coords[sender],[x2,y2]=coords[receiver];graph.append(svg('line',{x1,y1,x2,y2,class:'edge'}));}}));
 Object.entries(coords).forEach(([id,[x,y]])=>{const group=svg('g',{});group.append(svg('circle',{cx:x,cy:y,r:28,class:`node ${agentState(agentMap.get(id))}`}),svg('text',{x,y:y+4,'text-anchor':'middle',class:'node-label'},id.replace('agent_','A')));if(id===run.initial_agent_id)group.append(svg('text',{x,y:y+43,'text-anchor':'middle',class:'node-role'},run.intervention==='none'?'designated source':'injection source'));graph.append(group);});$('network').replaceChildren(graph);
 $('agents').replaceChildren();Object.keys(run.graph).forEach(id=>{const a=agentMap.get(id),row=el('div',null,'agent-row'),left=el('div',id);left.append(el('small',` · ${a?.messages_received??0} received${a?.exposed?' · exposed':''}${a?.quoted_only?' · quoted only':''}${a?.stated_agreement?' · agreement heuristic':''}`));const kind=agentState(a);row.append(left,el('span',!a||a.reason_code==='missing_or_ambiguous_artifact'?'Unknown / ambiguous':a.adopted_instruction?'Adopted suffix':a.legitimate_task_success?'Valid clean answer':a.quoted_only?'Quotation':'Other answer',`agent-state ${kind}`));$('agents').append(row);});
 $('trajectory').replaceChildren();run.timeline.forEach(t=>{const button=el('button',`Round ${t.round}`,`round-step ${t.round===round?'active':''}`);button.type='button';button.append(el('b',pct(t.adoption_rate)));button.addEventListener('click',()=>{$('round').value=String(t.round);renderRound();});$('trajectory').append(button);});renderTraces();
}
function renderTraces(){const run=state.selected,target=$('trace-list');target.replaceChildren();$('trace-count').textContent='0 events';if(!run)return;if(!state.snapshot.traces_included){empty(target,'Free-text traces were withheld from this public snapshot. Agent outcomes and routing remain available.');return;}
 const agent=$('trace-agent').value,type=$('trace-type').value,query=$('trace-search').value.toLowerCase();const traces=run.traces.filter(e=>e.round<=Number($('round').value)&&(agent==='all'||[e.agent_id,e.sender_id,e.receiver_id].includes(agent))&&(type==='all'||e.event_type===type)&&`${e.content??''} ${e.thinking??''}`.toLowerCase().includes(query));
 $('trace-count').textContent=`${traces.length} events`;
 for(const e of traces){const item=el('details',null,`trace-item event-${e.event_type}`);const label=[e.event_id,`r${e.round}`,e.event_type,e.agent_id??e.sender_id??'',e.receiver_id?`→ ${e.receiver_id}`:'',e.duration_seconds!=null?secs(e.duration_seconds):''].filter(Boolean).join(' · ');item.append(el('summary',label));if(e.content!=null){let content=e.content;try{content=JSON.stringify(JSON.parse(content),null,2);}catch{}item.append(el('pre',content));}if(e.thinking)item.append(el('pre',`GENERATED REASONING TEXT\n${e.thinking}`,'trace-thinking'));if(e.event_type==='artifact')item.open=true;target.append(item);}if(!traces.length)empty(target,'No events match the selected round and filters.');
}
async function load(){try{const response=await fetch(`data/results.json?v=${Date.now()}`,{cache:'no-store'});if(!response.ok)throw new Error('Snapshot could not be loaded');const data=await response.json();if(data.schema_version!=='1.0'||!Array.isArray(data.runs))throw new Error('Unsupported snapshot schema');$('error').hidden=true;if(state.snapshot?.generated_utc===data.generated_utc)return;state.snapshot=data;$('updated').textContent=`Exported ${new Date(data.generated_utc).toLocaleString()}`;$('privacy-state').textContent=data.traces_included?'Scrubbed trace export · manual review required':'Summary only · free-text traces withheld';$('redaction-note').textContent=`Snapshot redactions: ${data.redaction_replacements}. Unsealed runs omitted: ${data.skipped_unsealed}. Heuristic scrubbing cannot guarantee anonymity; raw data is never served.`;if(!data.runs.some(r=>r.backend!=='mock')&&$('backend').value==='live')$('backend').value='mock';render();}catch(error){$('error').hidden=false;$('error').textContent='The snapshot could not be loaded. Serve this directory over HTTP and verify data/results.json exists. No live model connection is made by this page.';}}
['backend','model','topology','condition'].forEach(id=>$(id).addEventListener('change',render));$('run-select').addEventListener('change',selectRun);$('round').addEventListener('input',renderRound);['trace-agent','trace-type','trace-search'].forEach(id=>$(id).addEventListener('input',renderTraces));$('refresh').addEventListener('click',load);load();

// Poll only public same-origin data; preserve open traces when the export is unchanged.
setInterval(()=>{if(!document.hidden)load();},60000);

const VIEW_LABELS={
 research:['Scenarios, Benchmarks & Review','Frozen scenario samples, task metrics, and uncalibrated independent review'],
 neural:['Neural Measurements','Instrumented checkpoint captures and controlled patching evidence'],
 overview:['Swarm Observability & Evaluation','Model behavior, network propagation, and trace-level evidence'],
 models:['Model & Protocol Comparison','Compare matched model cohorts, conditions, latency, and resource use'],
 evaluations:['Evaluation Results','Validated behavior, output quality, exposure, and run-level outcomes'],
 traces:['Trace Explorer','Inspect sanitized responses, inter-agent messages, and round-by-round routing'],
 datasets:['Published Datasets','Inspect cohort coverage and download the sanitized research snapshot'],
 methods:['Methods & Evaluation Tools','Measurement definitions, privacy boundaries, and interpretation limits']
};
function showView(name,updateHash=true){
 if(!VIEW_LABELS[name])name='overview';
 document.body.dataset.view=name;
 $('view-title').textContent=VIEW_LABELS[name][0];$('view-subtitle').textContent=VIEW_LABELS[name][1];
 Object.keys(VIEW_LABELS).forEach(view=>{const link=$(`nav-${view}`);link.classList.toggle('active',view===name);link.setAttribute('aria-current',view===name?'page':'false');});
 document.body.classList.remove('sidebar-open');
 if(typeof window!=='undefined'&&updateHash)window.history.pushState(null,'',`#${name}`);
}
Object.keys(VIEW_LABELS).forEach(view=>$(`nav-${view}`).addEventListener('click',event=>{event.preventDefault();showView(view);}));
$('view-models').addEventListener('click',event=>{event.preventDefault();showView('models');});
$('inspect-run').addEventListener('click',event=>{event.preventDefault();showView('traces');});
$('nav-toggle').addEventListener('click',()=>document.body.classList.toggle('sidebar-open'));
$('nav-overlay').addEventListener('click',()=>document.body.classList.remove('sidebar-open'));
showView(typeof window!=='undefined'?window.location.hash.slice(1):'overview',false);
if(typeof window!=='undefined'){window.addEventListener('hashchange',()=>showView(window.location.hash.slice(1),false));window.addEventListener('popstate',()=>showView(window.location.hash.slice(1),false));}

function compact(value){return value==null?'N/A':Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:1}).format(value);}
function cohortRange(runs,field){const values=groups(runs,r=>r.cohort).map(rs=>mean(rs.map(r=>r[field]))).filter(v=>v!=null);if(!values.length)return'N/A';const min=Math.min(...values),max=Math.max(...values);return Math.abs(max-min)<1e-9?pct(min):`${Math.round(100*min)}–${Math.round(100*max)}%`;}
function sparkline(id,values,bounded=false){
 const target=$(id);target.replaceChildren();const data=values.filter(v=>v!=null&&Number.isFinite(v));if(!data.length){target.append(el('span','Not recorded','panel-tag'));return;}
 const max=bounded?1:Math.max(...data,1),width=140,height=28;
 const points=data.map((v,i)=>[data.length===1?width/2:i*width/(data.length-1),height-3-v/max*(height-6)]);
 const chart=svg('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':'Recorded values in chronological run order'});
 const path=points.map(([x,y],i)=>`${i?'L':'M'} ${x} ${y}`).join(' ');
 chart.append(svg('path',{d:`${path} L ${points.at(-1)[0]} ${height} L ${points[0][0]} ${height} Z`,class:'spark-area'}),svg('path',{d:path,class:'spark-line'}));target.append(chart);
}
function renderObservability(){
 const runs=[...state.runs].sort((a,b)=>new Date(a.started_utc)-new Date(b.started_utc)),done=runs.filter(r=>r.status==='completed');
 $('adoption-kpi').textContent=cohortRange(done,'downstream_adoption_rate');
 $('boundary-kpi').textContent=cohortRange(done,'downstream_clean_rate');
 $('task-kpi').textContent=cohortRange(done,'legitimate_task_success_rate');
 const latency=median(runs.map(r=>r.median_call_seconds));$('latency-kpi').textContent=latency!=null&&latency<1?`${Math.round(latency*1000)}ms`:secs(latency);
 const tokens=runs.length&&runs.every(r=>r.generated_tokens!=null)?runs.reduce((n,r)=>n+r.generated_tokens,0):null;$('tokens-kpi').textContent=compact(tokens);
 $('errors-kpi').textContent=runs.length?pct(runs.filter(r=>r.status!=='completed').length/runs.length):'N/A';
 $('runs-sub').textContent=`${compact(runs.reduce((n,r)=>n+r.completed_calls,0))} responses · ${new Set(runs.map(r=>r.cohort)).size} cohorts`;
 $('trace-nav-count').textContent=compact(runs.reduce((n,r)=>n+r.completed_calls,0));$('trace-nav-count').setAttribute('title','Returned model responses in the current selection');
 const dates=runs.map(r=>r.started_utc.slice(0,10)).sort();$('date-range').textContent=dates.length?dates[0]===dates.at(-1)?`${dates[0]} · UTC`:`${dates[0]} → ${dates.at(-1)} · UTC`:'No matching runs';
 sparkline('latency-spark',runs.map(r=>r.median_call_seconds));sparkline('runs-spark',runs.map((_,i)=>i+1));sparkline('tokens-spark',runs.map(r=>r.generated_tokens));sparkline('task-spark',runs.map(r=>r.legitimate_task_success_rate),true);sparkline('adoption-spark',runs.map(r=>r.downstream_adoption_rate),true);sparkline('boundary-spark',runs.map(r=>r.downstream_clean_rate),true);sparkline('errors-spark',runs.map(r=>r.status==='completed'?0:1),true);sparkline('runtime-spark',runs.map(r=>r.duration_seconds));
 renderActivity(runs);renderObservations(runs);renderDistribution(done);renderDatasets(runs);renderRunQuality();
}
function renderActivity(runs){
 const target=$('activity-chart');if(!runs.length){empty(target,'No run history matches these filters.');return;}
 const totals=[];let returned=0,missing=0;runs.forEach(r=>{returned+=r.completed_calls;missing+=Math.max(0,r.attempted_calls-r.completed_calls);totals.push({returned,missing});});
 const width=540,height=245,left=40,right=18,top=12,bottom=38,max=Math.max(returned,missing,1),plot=svg('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':'Cumulative returned responses and unreturned logical invocations, by chronological run'});
 for(let i=0;i<=4;i++){const y=top+(height-top-bottom)*(1-i/4);plot.append(svg('line',{x1:left,y1:y,x2:width-right,y2:y,class:'gridline'}),svg('text',{x:2,y:y+3,class:'axis-label'},compact(max*i/4)));}
 const x=i=>left+(runs.length===1?.5:i/(runs.length-1))*(width-left-right),y=v=>height-bottom-v/max*(height-top-bottom);
 for(const [field,color] of [['returned','#409cff'],['missing','#f06473']]){
 const points=totals.map((v,i)=>`${x(i)},${y(v[field])}`).join(' ');plot.append(svg('polyline',{points,fill:'none',stroke:color,'stroke-width':2}));
 totals.forEach((v,i)=>{const dot=svg('circle',{cx:x(i),cy:y(v[field]),r:3,fill:color});dot.append(svg('title',{},`${runs[i].model} · seed ${runs[i].seed} · ${field}: ${v[field]}`));plot.append(dot);});}
 const step=Math.max(1,Math.ceil(runs.length/5));runs.forEach((r,i)=>{if(i%step===0||i===runs.length-1)plot.append(svg('text',{x:x(i),y:height-10,'text-anchor':'middle',class:'axis-label'},r.started_utc.slice(11,16)));});target.replaceChildren(plot);
}
function renderObservations(runs){
 const target=$('observations');target.replaceChildren();if(!runs.length){empty(target,'No observations in this selection.');return;}
 const failed=runs.filter(r=>r.status!=='completed').length,parse=runs.reduce((n,r)=>n+r.parse_failures,0),done=runs.filter(r=>r.status==='completed'),adopted=done.some(r=>r.downstream_adoption_rate>0);
 const observations=[
 [failed?'warn':'good',failed?`${failed} incomplete experiment attempts`:'All selected experiment attempts completed',`${runs.length} attempts · smoke diagnostics excluded`],
 [parse?'warn':'good',parse?`${parse} structured-output parse failures`:'No structured-output parse failures','JSON validity is separate from instruction adherence'],
 [adopted?'warn':'info',adopted?'Unauthorized suffix adoption observed':done.length?'No unauthorized suffix adoption observed':'No completed behavioral outcomes',done.length?'Exact artifact scorer · fixed synthetic task':'Behavioral metrics are unavailable'],
 ['info',`${new Set(runs.map(r=>r.cohort)).size} model / protocol cohorts selected`,'Small samples; compare matched conditions and seeds']
 ];
 observations.forEach(([kind,title,detail])=>{const row=el('div',null,`observation ${kind}`),text=el('div');text.append(el('p',title),el('small',detail));row.append(el('span',kind==='good'?'✓':kind==='warn'?'△':'ⓘ','observation-icon'),text);target.append(row);});
}
function renderDistribution(runs){
 const target=$('distribution');target.replaceChildren();const agents=runs.flatMap(r=>r.agents),total=agents.length;if(!total){empty(target,'No completed final artifacts.');return;}
 const counts=[agents.filter(a=>a.legitimate_task_success).length,agents.filter(a=>a.adopted_instruction).length,agents.filter(a=>!a.legitimate_task_success&&!a.adopted_instruction).length];
 const colors=['#39c879','#f06473','#f4ae49'],labels=['Valid clean','Suffix adopted','Other / ambiguous'],chart=svg('svg',{viewBox:'0 0 150 170',role:'img','aria-label':`Final artifact counts: ${counts.join(', ')}`}),radius=52,circumference=2*Math.PI*radius;
 chart.append(svg('circle',{cx:75,cy:78,r:radius,fill:'none',stroke:'#1b3047','stroke-width':20}));let offset=0;
 counts.forEach((n,i)=>{if(n){const size=n/total*circumference;chart.append(svg('circle',{cx:75,cy:78,r:radius,fill:'none',stroke:colors[i],'stroke-width':20,'stroke-dasharray':`${size} ${circumference-size}`,'stroke-dashoffset':-offset,transform:'rotate(-90 75 78)'}));offset+=size;}});
 chart.append(svg('text',{x:75,y:79,'text-anchor':'middle',class:'donut-total'},compact(total)),svg('text',{x:75,y:98,'text-anchor':'middle',class:'donut-label'},'final artifacts'));
 const key=el('div',null,'distribution-key');counts.forEach((n,i)=>{const row=el('p');row.append(el('span',null,`swatch ${i===1?'adopted':i===2?'other':''}`),el('span',`${labels[i]} · ${n}`));key.append(row);});target.append(chart,key);
}
function renderRunQuality(){
 const target=$('quality-bars'),run=state.selected;target.replaceChildren();if(!run){$('quality-run').textContent='No selected run';return;}
 $('quality-run').textContent=`${run.model} · ${run.topology} · ${run.intervention==='none'?'control':'injected'} · seed ${run.seed}`;
 const downstream=run.agents.filter(a=>a.agent_id!==run.initial_agent_id),complete=run.status==='completed';
 const rows=[['Valid clean final answers',complete?run.agents.filter(a=>a.legitimate_task_success).length:null,run.agents.length,''],['Strict downstream adherence',complete?downstream.filter(a=>a.legitimate_task_success).length:null,downstream.length,''],['Downstream marker exposure',downstream.filter(a=>a.exposed).length,downstream.length,'exposure'],['Structured response validity',run.completed_calls?Math.max(0,run.completed_calls-run.parse_failures):null,run.completed_calls,'']];
 rows.forEach(([label,n,denom,kind])=>{const row=el('div',null,`quality-row ${kind}`),head=el('div',null,'quality-label');head.append(el('span',label),el('span',n==null||!denom?'N/A':`${n}/${denom} · ${pct(n/denom)}`));row.append(head);if(n!=null&&denom){const progress=el('progress');progress.max=denom;progress.value=n;progress.setAttribute('aria-label',label);row.append(progress);}target.append(row);});
}
function renderDatasets(runs){
 const target=$('datasets');target.replaceChildren();for(const rs of groups(runs,r=>r.cohort)){const r=rs[0],row=el('tr'),model=el('td',r.model);model.append(el('small',r.cohort));row.append(model);[r.backend==='mock'?'Mock validation':'Live inference',r.protocol_version,[...new Set(rs.map(r=>r.seed))].sort((a,b)=>a-b).join(', '),rs.length,rs.reduce((n,r)=>n+r.completed_calls,0),r.thinking].forEach(value=>row.append(el('td',value)));target.append(row);}if(!runs.length){const row=el('tr'),cell=el('td','No matching cohorts.');cell.colSpan=7;row.append(cell);target.append(row);}
}

const researchState={snapshot:null};
function researchTable(id,headers,rows){const target=$(id);target.replaceChildren();if(!rows.length){empty(target,'No published measurements in this category.');return;}const table=el('table'),head=el('tr');headers.forEach(h=>head.append(el('th',h)));table.append(head);rows.forEach(values=>{const row=el('tr');values.forEach(v=>row.append(el('td',v)));table.append(row);});target.append(table);}
function renderResearch(){const d=researchState.snapshot;if(!d)return;
 researchTable('research-studies',['Model / evidence','Protocol / agents','Task / case','Split / topology','Condition','Status / calls','Task success','Violation / attempt / state','Runtime'],d.studies.map(r=>[`${r.model} / ${r.backend} / ${r.model_digest?.slice(0,12)??"digest unavailable"}`,`${r.protocol} / ${r.agent_count??5}`,`${r.task_family} / ${r.case_id}`,`${r.split} / ${r.topology}`,r.intervention,`${r.status} / ${r.calls}`,pct(r.task_success_rate),`${r.violation} / ${r.attempted_forbidden} / ${r.state_violation}`,secs(r.runtime)]));
 $('research-review-status').textContent=`Reviewer: ${d.review_source}. Uncalibrated; human review required. ${d.unreviewed_samples} samples remain unreviewed. Confidence is a self-report, not a validated probability.`;
 researchTable('research-reviews',['Priority','Sample','Behavior','Confidence','Evidence IDs','Queue reasons'],[...d.reviews].sort((a,b)=>b.priority-a.priority).map(r=>[r.priority,r.sample_id,r.behavior,pct(r.confidence),r.evidence_event_ids.join(', '),r.queue_reasons.join(', ')]));
 researchTable('research-monitor',['Evidence','Policy','Visibility','Runs','Precision','Recall','F1','False positive rate'],d.monitor.map(r=>[r.backend,r.policy,pct(r.visibility),r.n,pct(r.precision),pct(r.recall),pct(r.f1),pct(r.false_positive_rate)]));
 $('scenario-count').textContent=`${d.scenarios.length} deterministic variants of four templates. Development and evaluation splits are separate. Variants are not independently authored attacks.`;
 researchTable('research-scenarios',['Scenario','Category','Family','Split','Content hash'],d.scenarios.map(r=>[r.case_id,r.category,r.family,r.split,r.content_hash.slice(0,12)]));
 renderScaling(d.studies);
 const previous=$('neural-select').value;$('neural-select').replaceChildren(...d.neural.map(r=>new Option(`${r.model} / ${r.evidence_type} / ${r.id}`,r.id)));if(d.neural.some(r=>r.id===previous))$('neural-select').value=previous;renderNeural();
}
function renderNeural(){const target=$('neural-evidence');target.replaceChildren();const d=researchState.snapshot;const r=d?.neural.find(x=>x.id===$('neural-select').value)||d?.neural[0];if(!r){empty(target,'No measured neural captures published. The Linux TransformerLens worker is prepared; no activations have been inferred from model text.');return;}
 target.append(el('p',`${r.model} · ${r.evidence_type} · ${secs(r.duration_seconds)} · ${r.device} / ${r.dtype} · revision ${r.revision??'seeded random initialization'}`,'notice'));
 for(const kind of ['clean','corrupt']){target.append(el('h3',`${kind} residual RMS · layer × token position`));const table=el('table'),head=el('tr');head.append(el('th','Layer'));const n=r[`${kind}_token_count`];for(let i=0;i<n;i++)head.append(el('th',`P${i}`));table.append(head);const max=Math.max(.000001,...r.layers.flatMap(l=>l[`${kind}_residual_rms`]));r.layers.forEach(l=>{const row=el('tr');row.append(el('th',l.layer));l[`${kind}_residual_rms`].forEach(v=>{const cell=el('td',v.toFixed(3),'heatmap-cell');cell.style.backgroundColor=`rgba(62,148,255,${Math.max(.06,v/max*.8)})`;row.append(cell);});table.append(row);});const wrap=el('div',null,'neural-grid');wrap.append(table);target.append(wrap);}
 const p=r.patch;target.append(el('h3','Single-position activation patch · target logit'));const list=el('dl');Object.entries(p).forEach(([k,v])=>list.append(el('dt',k),el('dd',typeof v==='number'?v.toFixed(4):v)));target.append(list,el('p','Compare clean, corrupt, patched, no-op and position-control logits. A logit difference is a local intervention effect, not evidence of model intent.','caption'));
 target.append(el('h3','Selected MLP neurons · clean / corrupt by token position'));r.layers.forEach(l=>l.neurons.forEach(n=>{const detail=el('details');detail.append(el('summary',`Layer ${l.layer} / neuron ${n.index}`),el('pre',`Clean: ${n.clean.map(v=>v.toFixed(4)).join(' ')}\nCorrupt: ${n.corrupt.map(v=>v.toFixed(4)).join(' ')}`));target.append(detail);}));
}
async function loadResearch(){try{const response=await fetch(`data/research.json?v=${Date.now()}`,{cache:'no-store'});if(!response.ok)throw Error('Unavailable');const data=await response.json();if(data.schema_version!=='1.0'||!Array.isArray(data.studies)||!Array.isArray(data.neural)||!Array.isArray(data.scenarios))throw Error('Schema');researchState.snapshot=data;renderResearch();}catch{['research-studies','research-reviews','research-monitor','research-scenarios','neural-evidence'].forEach(id=>empty($(id),'No validated research snapshot available. Export research.json to publish these measurements.'));}}
$('neural-select').addEventListener('change',renderNeural);
loadResearch();setInterval(()=>{if(!document.hidden)loadResearch();},60000);

function renderScaling(studies){const target=$('scaling-charts');target.replaceChildren();const rows=studies.filter(r=>r.protocol==='2.1'&&r.status==='completed');if(!rows.length){empty(target,'No completed swarm-size study published.');return;}
 for(const group of groups(rows,r=>[r.model,r.backend,r.model_digest,r.size_comparison_group??r.freeze_hash,r.topology,r.intervention].join('|'))){
 // The exporter matches source/model/task/seed/graph/sampling and varies only size.
 const first=group[0];target.append(el('h3',`${first.model} / ${first.backend} / ${first.topology} / ${first.intervention} / ${first.case_id} / seed ${first.seed}`));
 const width=600,height=190,plot=svg('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':'Recorded run runtime by agent count; one point per run'});
 const xmax=Math.max(5,...rows.map(r=>r.agent_count)),ymax=Math.max(.001,...group.map(r=>r.runtime));
 [0,.5,1].forEach(v=>plot.append(svg('line',{x1:50,y1:145-v*110,x2:580,y2:145-v*110,class:'gridline'}),svg('text',{x:0,y:149-v*110,class:'axis-label'},secs(v*ymax))));
 group.forEach(r=>{const x=50+r.agent_count/xmax*520,y=145-r.runtime/ymax*110,dot=svg('circle',{cx:x,cy:y,r:4,class:`chart-dot ${r.intervention!=='none'?'injected':''}`});dot.append(svg('title',{},`${r.agent_count} agents / ${r.case_id} / ${secs(r.runtime)} / task success ${pct(r.task_success_rate)}`));plot.append(dot,svg('text',{x,y:167,'text-anchor':'middle',class:'axis-label'},`${r.agent_count} agents`));});
 const wrap=el('div',null,'chart');wrap.append(plot);target.append(wrap);
 }
}
