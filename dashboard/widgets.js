'use strict';
// Framework-free plotting primitives. Inputs are numeric series and labels, never model HTML.
const EvidenceWidgets=(()=>{
 const NS='http://www.w3.org/2000/svg';
 const node=(tag,attrs={},text)=>{const n=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,String(v)));if(text!=null)n.textContent=String(text);return n;};
 function canvas(target,label,width=620,height=240){const p=node('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':label});target.replaceChildren(p);return p;}
 function bars(target,items,{label='Measured values',signed=false}={}){const h=Math.max(85,items.length*33+40),p=canvas(target,label,620,h),max=Math.max(.00001,...items.map(x=>Math.abs(x.value))),zero=signed?360:220,span=signed?200:350;
 items.forEach((r,i)=>{const y=25+i*33,w=Math.abs(r.value)/max*span;p.append(node('text',{x:0,y:y+12,class:'axis-label'},r.label),node('rect',{x:r.value<0?zero-w:zero,y,width:Math.max(.4,w),height:16,fill:r.color??'#409cff',rx:2}),node('text',{x:zero+(r.value<0?-w-6:w+6),y:y+12,'text-anchor':r.value<0?'end':'start',class:'axis-label'},r.value.toFixed(4)));});p.append(node('line',{x1:zero,y1:10,x2:zero,y2:h-10,class:'gridline'}));}
 function histogram(target,series,{bins=10,label='Activation histogram'}={}){const all=series.flatMap(s=>s.values).filter(Number.isFinite);const p=canvas(target,label);if(!all.length){p.append(node('text',{x:30,y:80,class:'axis-label'},'No measured activation samples'));return;}
 const lo=Math.min(...all),hi=Math.max(...all),range=hi-lo||1,counts=series.map(s=>{const c=Array(bins).fill(0);s.values.forEach(v=>{if(Number.isFinite(v))c[Math.min(bins-1,Math.floor((v-lo)/range*bins))]++;});return c;}),max=Math.max(1,...counts.flat());
 counts.forEach((c,j)=>c.forEach((n,i)=>{const w=520/bins/series.length,x=45+i*520/bins+j*w,y=185-n/max*145;p.append(node('rect',{x,y,width:Math.max(1,w-1),height:185-y,fill:series[j].color??'#409cff',opacity:.8}));}));
 p.append(node('text',{x:45,y:210,class:'axis-label'},lo.toFixed(3)),node('text',{x:565,y:210,'text-anchor':'end',class:'axis-label'},hi.toFixed(3)),node('text',{x:45,y:20,class:'axis-label'},`Counts · ${all.length} recorded values`));}
 function confusion(target,{tp,fp,tn,fn}){const p=canvas(target,'Monitor confusion matrix: rows actual, columns predicted',420,260),cells=[['TN',tn,90,45],['FP',fp,230,45],['FN',fn,90,130],['TP',tp,230,130]],max=Math.max(1,tp,fp,tn,fn);
 cells.forEach(([name,value,x,y])=>{p.append(node('rect',{x,y,width:130,height:75,rx:5,fill:'#2d8ed0',opacity:.15+.8*value/max}),node('text',{x:x+65,y:y+32,'text-anchor':'middle',fill:'#bedcf3'},name),node('text',{x:x+65,y:y+57,'text-anchor':'middle',fill:'#fff'},value));});p.append(node('text',{x:90,y:235,class:'axis-label'},'Predicted negative'),node('text',{x:235,y:235,class:'axis-label'},'Predicted positive'),node('text',{x:0,y:85,class:'axis-label'},'Actual −'),node('text',{x:0,y:170,class:'axis-label'},'Actual +'));}
 function scatter(target,series,{label='Measured points',xLabel='Position',yLabel='Value',includeZero=false}={}){
 const all=series.flatMap(s=>s.points).filter(v=>Number.isFinite(v.x)&&Number.isFinite(v.y)),p=canvas(target,label,660,300);
 if(!all.length){p.append(node('text',{x:35,y:95,class:'axis-label'},'No defined measurements for this selection'));return;}
 const extent=(values,zero)=>{let lo=Math.min(...values),hi=Math.max(...values);if(zero){lo=Math.min(0,lo);hi=Math.max(0,hi);}const pad=(hi-lo||Math.max(Math.abs(lo)*.1,.01))*.12;return [lo-pad,hi+pad];};
 const [xmin,xmax]=extent(all.map(v=>v.x),false),[ymin,ymax]=extent(all.map(v=>v.y),includeZero);
 const xx=v=>75+(v-xmin)/(xmax-xmin)*540,yy=v=>230-(v-ymin)/(ymax-ymin)*175;
 const fmt=v=>Math.abs(v)<1e-10?'0':String(Number(v.toPrecision(3)));
 for(let i=0;i<5;i++){const y=ymin+(ymax-ymin)*i/4;p.append(node('line',{x1:75,y1:yy(y),x2:615,y2:yy(y),class:'gridline'}),node('text',{x:64,y:yy(y)+4,'text-anchor':'end',class:'axis-label'},fmt(y)));const x=xmin+(xmax-xmin)*i/4;p.append(node('text',{x:xx(x),y:250,'text-anchor':'middle',class:'axis-label'},fmt(x)));}
 if(ymin<=0&&ymax>=0)p.append(node('line',{x1:75,y1:yy(0),x2:615,y2:yy(0),stroke:'#90a9c4','stroke-dasharray':'4 4'}));
 series.forEach((s,index)=>{const points=s.points.filter(v=>Number.isFinite(v.x)&&Number.isFinite(v.y));if(s.connect&&points.length>1)p.append(node('polyline',{points:points.map(v=>`${xx(v.x)},${yy(v.y)}`).join(' '),fill:'none',stroke:s.color??'#409cff','stroke-width':2,opacity:.8}));
 const clusters=new Map();points.forEach(v=>{const key=JSON.stringify([v.x,v.y]);if(!clusters.has(key))clusters.set(key,[]);clusters.get(key).push(v);});
 for(const cluster of clusters.values()){const v=cluster[0],dot=node('circle',{cx:xx(v.x),cy:yy(v.y),r:cluster.length>1?8:5,fill:s.color??'#409cff',stroke:'#091a2b','stroke-width':1.5,opacity:.9,tabindex:0});dot.append(node('title',{},cluster.map(q=>q.label??`${s.label??''}: ${q.x}, ${q.y}`).join('\n')));dot.setAttribute('aria-label',`${cluster.length} measurement(s): ${v.x}, ${v.y}`);p.append(dot);if(cluster.length>1)p.append(node('text',{x:xx(v.x)+12,y:yy(v.y)-9,class:'axis-label'},`×${cluster.length}`));}
 if(s.label)p.append(node('text',{x:75+index*180,y:29,fill:s.color??'#409cff',class:'axis-label'},s.label));});
 p.append(node('text',{x:75,y:12,class:'axis-label'},yLabel),node('text',{x:340,y:276,'text-anchor':'middle',class:'axis-label'},xLabel),node('text',{x:75,y:296,class:'axis-label'},`${all.length} measurements · fitted axes · ×n denotes exact overlaps`));
 }

 return Object.freeze({bars,histogram,confusion,scatter});
})();
