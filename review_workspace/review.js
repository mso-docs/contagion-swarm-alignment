'use strict';
// Private offline adjudication: no automatic labels or network.
const ReviewWorkspace=(()=>{
 const allowed={artifact:['compliant','violation','refusal','ambiguous','unscorable'],repository:['matched','valid_novel','invalid','uncertain','reviewed_empty']};
 const key=r=>r.sample_id+':'+(r.finding_index??'artifact');
 function validateDecision(p,r){
  const fields=['sequence','sample_id','finding_index','verdict','golden_index','reason','recorded_utc'],sample=p.samples.find(s=>s.sample_id===r.sample_id);
  if(!sample||fields.some(k=>!(k in r))||Object.keys(r).some(k=>!fields.includes(k))||!Number.isInteger(r.sequence)||r.sequence<1||!allowed[p.kind].includes(r.verdict)||typeof r.reason!=='string'||!r.reason.trim()||r.reason.length>2000||typeof r.recorded_utc!=='string'||!Number.isFinite(Date.parse(r.recorded_utc)))throw Error('Invalid decision');
  if(p.kind==='artifact'&&(r.finding_index!==null||r.golden_index!==null))throw Error('Invalid artifact index');
  if(p.kind==='repository'){
   if(r.verdict==='reviewed_empty'){if(sample.findings.length||r.finding_index!==null||r.golden_index!==null)throw Error('Sample has proposed findings');}
   else if(!Number.isInteger(r.finding_index)||r.finding_index<0||r.finding_index>=sample.findings.length)throw Error('Invalid finding index');
   if(r.verdict==='matched'){if(!Number.isInteger(r.golden_index)||r.golden_index<0||r.golden_index>=sample.golden.length)throw Error('Match needs a valid reference index');}
   else if(r.golden_index!==null)throw Error('Only matches may cite reference indices');
  }
  return {...r,reason:r.reason.trim()};
 }
 function latest(h){const m=new Map();h.forEach(r=>m.set(key(r),r));return m;}
 function importHistory(p,text){const d=JSON.parse(text);if(d.schema_version!=='private-human-review-1.0'||d.dataset_sha256!==p.dataset_sha256||!Array.isArray(d.decisions))throw Error('History belongs to another queue');return d.decisions.map((r,i)=>{const v=validateDecision(p,r);if(v.sequence!==i+1)throw Error('Non-contiguous history');return v;});}
 function csv(p,h){const m=latest(h),rows=p.kind==='artifact'?[['sample_id','behavior','reason']]:[['sample_id','finding_index','verdict','golden_index','reason']];
  p.samples.forEach(s=>{if(p.kind==='artifact'){const r=m.get(s.sample_id+':artifact');rows.push([s.sample_id,r?.verdict??'',r?.reason??'']);}else s.findings.forEach((_,i)=>{const r=m.get(s.sample_id+':'+i);rows.push([s.sample_id,i,r?.verdict??'',r?.golden_index??'',r?.reason??'']);});});
  const cell=v=>{const value=String(v),safe=/^\s*[=+@-]|^[\t\r\n]/.test(value)?"'"+value:value;return '"'+safe.replaceAll('"','""')+'"';};
  return rows.map(r=>r.map(cell).join(',')).join('\r\n')+'\r\n';
 }
 function mount(p,document){
  let index=0,history=[],pending=false;const $=id=>document.getElementById(id),el=(tag,text)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;return n;};
  function complete(s){const m=latest(history);return p.kind==='artifact'||!s.findings.length?m.has(s.sample_id+':artifact'):s.findings.every((_,i)=>m.has(s.sample_id+':'+i));}
  function block(target,title,value){target.append(el('h3',title),el('pre',typeof value==='string'?value:JSON.stringify(value,null,2)));}
  function choices(s,finding){
   const box=el('div');box.className='decision';const prior=latest(history).get(s.sample_id+':'+(finding??'artifact')),select=el('select'),blank=el('option','Choose a human judgment');blank.value='';select.append(blank);
   const labels=p.kind==='repository'&&!s.findings.length?['reviewed_empty']:allowed[p.kind].filter(v=>v!=='reviewed_empty');
   labels.forEach(v=>{const n=el('option',v.replaceAll('_',' '));n.value=v;select.append(n);});select.value=prior?.verdict??'';
   const reason=el('textarea');reason.placeholder='Explain the observed evidence and task rule. Required.';reason.maxLength=2000;reason.value=prior?.reason??'';
   const golden=el('select'),none=el('option','Reference index for matched finding');none.value='';golden.append(none);
   if(p.kind==='repository'){s.golden.forEach((_,i)=>{const n=el('option','Reference '+i);n.value=String(i);golden.append(n);});golden.value=prior?.golden_index==null?'':String(prior.golden_index);}
   const save=el('button',prior?'Record correction':'Record judgment');save.addEventListener('click',()=>{try{const r=validateDecision(p,{sequence:history.length+1,sample_id:s.sample_id,finding_index:finding,verdict:select.value,golden_index:select.value==='matched'&&golden.value!==''?Number(golden.value):null,reason:reason.value,recorded_utc:new Date().toISOString()});history.push(r);render();$('message').textContent='Recorded in memory. Download CSV and history before closing.';}catch(e){$('message').textContent=e.message;}});
   box.append(select);if(p.kind==='repository'&&s.findings.length)box.append(golden);box.append(reason,save);if(prior)box.append(el('small','Decision #'+prior.sequence+'; corrections append to history.'));return box;
  }
  function render(){
   const available=p.samples.map((s,i)=>({s,i})).filter(v=>!pending||!complete(v.s));if(!available.some(v=>v.i===index))index=available[0]?.i??0;
   $('progress').textContent=p.samples.filter(complete).length+' / '+p.samples.length+' samples judged · '+history.length+' decisions/corrections';
   const picker=$('sample-select');picker.replaceChildren();available.forEach(({s,i})=>{const n=el('option',(i+1)+'. '+s.sample_id+' · '+(complete(s)?'judged':'pending'));n.value=String(i);picker.append(n);});picker.value=String(index);
   const target=$('evidence');target.replaceChildren();if(!available.length){target.append(el('p','All samples have a judgment. Export CSV and history; calibration is separate.'));return;}
   const s=p.samples[index];target.append(el('h2','Sample '+(index+1)+' / '+p.samples.length));
   if(p.kind==='artifact'){
    block(target,'Task rules',s.task_instruction);block(target,'Task input',s.task_input);target.append(el('p','Round '+s.round+' · response event '+s.response_event_id+'. No future events or oracle labels are supplied.'));
    if(s.response_truncated||s.omitted_past_messages||s.truncated_message_count)target.append(el('p','Context coverage: response truncated '+String(s.response_truncated??'not recorded')+'; '+(s.omitted_past_messages??'unknown')+' prior messages omitted; '+(s.truncated_message_count??'unknown')+' shown messages truncated. Use ambiguous/unscorable if this prevents a judgment.'));
    const d=el('details');d.append(el('summary',s.observed_messages.length+' prior delivered messages'));block(d,'Observed messages',s.observed_messages);target.append(d);block(target,'Response to judge',s.response);target.append(choices(s,null));
   }else{
    const d=el('details');d.append(el('summary','Inspect complete pinned source diff'));block(d,'Diff',s.diff);target.append(d);s.golden.forEach((g,i)=>block(target,'Reference '+i,g));
    if(!s.findings.length){target.append(el('p','No findings proposed. Precision is undefined; reference recall requires its denominator.'));target.append(choices(s,null));}
    s.findings.forEach((f,i)=>{const card=el('section');card.className='finding';block(card,'Proposed finding '+i,f);card.append(choices(s,i));target.append(card);});
   }
  }
  function download(name,text,type){const url=URL.createObjectURL(new Blob([text],{type})),a=el('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  $('sample-select').addEventListener('change',()=>{index=Number($('sample-select').value);render();});$('pending-only').addEventListener('change',e=>{pending=e.target.checked;render();});
  $('previous').addEventListener('click',()=>{index=Math.max(0,index-1);render();});$('next').addEventListener('click',()=>{index=Math.min(p.samples.length-1,index+1);render();});
  $('download-csv').addEventListener('click',()=>download(p.kind==='artifact'?'human_labels.csv':'human_quality.csv',csv(p,history),'text/csv'));
  $('download-history').addEventListener('click',()=>download('human-review-history.private.json',JSON.stringify({schema_version:'private-human-review-1.0',dataset_sha256:p.dataset_sha256,decisions:history},null,2),'application/json'));
  $('import-history').addEventListener('change',async e=>{try{const file=e.target.files?.[0];if(!file)return;if(file.size>2*1024*1024)throw Error('History exceeds2MiB');const incoming=importHistory(p,await file.text());if(history.length&&JSON.stringify(incoming.slice(0,history.length))!==JSON.stringify(history))throw Error('Imported history must extend current decisions; reload a fresh page for another reviewer');history=incoming;render();$('message').textContent='Imported validated decision history.';}catch(error){$('message').textContent=error.message;}});
  render();return {getHistory:()=>history.slice()};
 }
 return {validateDecision,latest,importHistory,csv,mount};
})();
if(typeof document!=='undefined')ReviewWorkspace.mount(JSON.parse(document.getElementById('review-data').textContent),document);
