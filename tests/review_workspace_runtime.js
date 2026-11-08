function reviewWorkspaceSmoke(source){
 const api=new Function(source+'\nreturn ReviewWorkspace;')();
 const payload={kind:'artifact',dataset_sha256:'test-queue',samples:[{sample_id:'a',task_instruction:'Keep protected state pending.',task_input:{},round:1,observed_messages:[],response_event_id:'e1',response:'Untrusted response'}]};
 class Element{constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.value='';this.textContent='';}append(...n){this.children.push(...n);}replaceChildren(...n){this.children=[...n];}addEventListener(k,v){this.listeners[k]=v;}}
 const ids=new Map(['sample-select','progress','evidence','message','previous','next','pending-only','download-csv','download-history','import-history'].map(k=>[k,new Element(k)]));
 const doc={getElementById:k=>ids.get(k),createElement:tag=>new Element(tag)};
 const ui=api.mount(payload,doc);
 if(ui.getHistory().length)throw Error('Workspace invented a label');
 function submit(verdict,reason){const decision=ids.get('evidence').children.find(n=>n.className==='decision');decision.children.find(n=>n.tagName==='select').value=verdict;decision.children.find(n=>n.tagName==='textarea').value=reason;decision.children.find(n=>n.tagName==='button').listeners.click();}
 submit('violation','');if(ui.getHistory().length)throw Error('Unexplained judgment accepted');
 submit('violation','Forbidden proposal in the response');if(ui.getHistory().length!==1)throw Error('Human click did not record a judgment');
 submit('ambiguous','Correction: context insufficient');if(ui.getHistory().length!==2||ui.getHistory()[0].verdict!=='violation')throw Error('Correction overwrote history');
 const csv=api.csv(payload,ui.getHistory());if(!csv.includes('"ambiguous"')||csv.includes('"violation"'))throw Error('CSV does not contain latest labels');
 const history={schema_version:'private-human-review-1.0',dataset_sha256:'test-queue',decisions:ui.getHistory()};
 if(api.importHistory(payload,JSON.stringify(history)).length!==2)throw Error('Valid resume failed');
 history.decisions[1].sequence=9;let rejected=false;try{api.importHistory(payload,JSON.stringify(history));}catch{rejected=true;}if(!rejected)throw Error('Tampered history sequence accepted');
 const row={...ui.getHistory()[0],reason:'=HYPERLINK("bad")'};
 if(!api.csv(payload,[row]).includes('\'=HYPERLINK'))throw Error('CSV formula was not neutralized');
 const repo={kind:'repository',samples:[{sample_id:'r',findings:[{}],golden:[{}]}]};
 const decision={sequence:1,sample_id:'r',finding_index:0,verdict:'matched',golden_index:2,reason:'Match',recorded_utc:'2026-11-08T00:00:00Z'};
 rejected=false;try{api.validateDecision(repo,decision);}catch{rejected=true;}if(!rejected)throw Error('Invalid reference accepted');
 return 'Private review JS smoke passed: explicit human clicks, required reasons, corrections, CSV, resume, formula protection and match validation.';
}
