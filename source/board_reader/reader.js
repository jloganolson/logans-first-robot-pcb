(() => {
  const root = document.getElementById('trace-reader');
  const get = id => document.getElementById('br-' + id);
  const {detail, nets, owners, board, sheetPins, sheetImage} = JSON.parse(get('data').textContent);
  const left = get('left'), right = get('right');
  const splitPin = key => key.split('.');
  const pinData = key => { const [ref,pin] = splitPin(key); return detail[ref]?.pins[pin]; };
  const netId = name => Object.keys(nets).find(n => nets[n] === name);
  const xml = str => String(str).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;');
  const option = (value,label) => new Option(label,value);
  const routes = {
    motor: [
      ['J1.2','VBAT leaves J1 pin 2. Follow the filled copper to pin 2 of both fuse holders.'],
      ['F1.2','You are still on VBAT at F1 pin 2. The four same-numbered holes contact one fuse terminal.'],
      ['F1.1','Cross the removable fuse to pin 1. The copper beyond the fuse has a new name, VMOT.'],
      ['J2.2','VMOT reaches J2 pin 2 and leaves for the wheel controller through the harness.'],
      ['J2.1','Current returns from the controller to J2 pin 1. In1.Cu shows the ground plane.'],
      ['J1.1','J1 pin 1 carries the return to battery negative. Both connector ground pins join the same plane.']
    ],
    logic: [
      ['J1.2','Start at raw battery positive, VBAT.'],['F2.2','F2 pin 2 receives the same VBAT copper as F1.'],
      ['F2.1','Across the logic fuse, pin 1 becomes VBAT_L. D1 and C1 connect from this node to GND.'],
      ['Q1.1','VBAT_L reaches all three source pads of Q1. In normal forward operation the power current crosses the MOSFET.'],
      ['Q1.5','Q1’s drain is on VIN. U1 also senses this node at pin 4.'],['TP1.1','TP1 exposes VIN for a measurement. C3 and C4 connect VIN to GND near the input.']
    ],
    gate: [
      ['U1.6','U1 senses VBAT_L at ANODE. The same net enables U1 at pin 3.'],
      ['U1.4','CATHODE senses the protected VIN side of Q1.'],
      ['U1.5','The GATE output connects to Q1_G. This short trace drives the gate. The motor current takes a separate path.'],
      ['Q1.4','Q1 pin 4 receives the drive signal. Its voltage relative to the source controls the channel.'],
      ['C2.1','C2 pin 1 is connected to U1.1 VCAP. Its other end returns to VBAT_L.']
    ]
  };
  const state = {key:'J1.2',n:netId('VBAT'),mode:'wired',route:'motor',step:0};
  const selectedRefs = new Set();
  const views = new Map();
  const sectionBox = [-5,-2,52,85];
  const fullBox = [-5,-4,238,116];
  function view(svg,box) {
    views.set(svg,box); svg.setAttribute('viewBox', box.map(x => x.toFixed(5)).join(' '));
  }
  function zoom(svg, factor, point) {
    const [x,y,w,h]=views.get(svg);
    const lower = svg===right ? 2 : state.mode==='sheet' ? 7 : 68;
    const upper = svg===right ? 370 : state.mode==='sheet' ? 1550 : 770;
    const f=Math.min(upper,Math.max(lower,w*factor))/w;
    const [px,py]=point||[x+w/2,y+h/2];
    view(svg,[px+(x-px)*f,py+(y-py)*f,w*f,h*f]);
  }
  function origin(svg,event) {
    const p=new DOMPoint(event.clientX,event.clientY);
    const v=p.matrixTransform(svg.getScreenCTM().inverse());return [v.x,v.y];
  }
  function focusPCB(key) {
    const data=pinData(key),[ref]=splitPin(key);
    if(!data)return;
    const [x,y]=data.b[0];
    const span=/^(J|F\d|L\d)/.test(ref)?28:17;
    view(right,[x-span/2,y-span/2,span,span]);
  }
  function focusSheet(ref) {
    const [sx,sy]=detail[ref].sheet;
    const points=Object.values(detail[ref].pins).filter(p=>p.s).map(p=>p.s);
    const dx=Math.max(6,...points.map(p=>Math.abs(p[0]-sx)));
    const dy=Math.max(6,...points.map(p=>Math.abs(p[1]-sy)));
    view(left,[sx-dx-12,sy-dy-9,2*dx+29,2*dy+18]);
  }
  function text(x,y,s,size=13,cls='',anchor='start') {
    return '<text x="'+x+'" y="'+y+'" font-size="'+size+'" class="'+cls+'" text-anchor="'+anchor+'">'+xml(s)+'</text>';
  }
  function wire(name,d,x,y,label=name) {
    return '<g data-n="'+netId(name)+'" class="wiregroup"><path d="'+d+'" class="netwire"/><path d="'+d+'" class="wirehit"/>'+text(x,y,label,12)+'</g>';
  }
  function pin(key,x,y,label,dx=0,dy=-11,anchor='middle') {
    const p=pinData(key);if(!p)throw new Error('Unknown schematic pin '+key);
    selectedRefs.add(key);
    return '<g class="wiredpin" data-n="'+p.n+'" data-pin="'+key+'"><title>'+key+' · '+nets[p.n]+'</title><circle class="terminal" cx="'+x+'" cy="'+y+'" r="4"/>'+text(x+dx,y+dy,label,11,'',anchor)+'<circle class="pinHit" cx="'+x+'" cy="'+y+'" r="8"/></g>';
  }
  const box=(x,y,w,h)=>'<rect class="schemBody" x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="2"/>';
  const strokes=d=>'<path d="'+d+'" fill="none" stroke="#263f42" stroke-width="2"/>';
  function wired() {
    let s=text(13,22,'Battery distribution',16,'schref');
    s+=box(15,70,66,55)+text(30,94,'J1',15,'schref')+text(24,113,'battery',11);
    s+=wire('VBAT','M81 83 H128 V51 H196 M128 83 V138 H196',99,68,'VBAT')+
       wire('VMOT','M244 51 H456',307,42)+wire('GND','M81 114 H102 V187 H540 V97 H471 V84',260,179,'GND · common return');
    s+=box(456,34,78,50)+text(477,58,'J2',15,'schref')+text(475,73,'motor',11);
    for(const [r,y,amp] of [['F1',51,'30 A'],['F2',138,'20 A']]){
      s+=box(196,y-7,48,14)+strokes('M196 '+y+'h48')+text(196,y-16,r+' · '+amp,13,'schref')+
        pin(r+'.2',196,y,'2',-8,15)+pin(r+'.1',244,y,'1',8,15);
    }
    s+=wire('VBAT_L','M244 138 H356',261,125)+box(356,125,53,26)+text(368,143,'Q1',14,'schref')+
       wire('VIN','M409 138 H512',464,127)+pin('Q1.1',356,138,'S 1–3',-6,17)+pin('Q1.5',409,138,'D 5',5,17)+pin('TP1.1',512,138,'TP1',0,19);
    s+=pin('J1.2',81,83,'2',-9,-5)+pin('J1.1',81,114,'1',-10,-3)+pin('J2.2',456,51,'2',-8,-7)+pin('J2.1',471,84,'1',12,15);
    s+=wire('Q1_G','M383 151 V167 H422',425,171,'Q1_G')+pin('Q1.4',383,151,'4',12,11);
    s+=text(13,222,'Logic input and U1 sense pins',16,'schref');
    s+=text(13,243,'Matching net names join across these two circuits.',12);
    s+=box(207,270,135,121)+text(274,263,'U1 · LM74700',14,'schref','middle');
    const rows=[['U1.6',207,281,67,'VBAT_L','6 ANODE'],['U1.3',207,318,67,'VBAT_L','3 EN'],['U1.2',207,368,67,'GND','2 GND'],['U1.4',342,281,458,'VIN','4 CATHODE'],['U1.5',342,318,458,'Q1_G','5 GATE'],['U1.1',342,368,458,'U1_VCAP','1 VCAP']];
    for(const [key,x,y,end,net,name] of rows){
      s+=wire(net,'M'+x+' '+y+'H'+end, x===207?end:end-70,y-6)+pin(key,x,y,name,x===207?7:-7,4,x===207?'start':'end');
    }
    return s;
  }
  const wiredMarkup=wired();
  const distributionPins=new Set(selectedRefs);
  selectedRefs.clear();
  function protection(){
    let s=text(15,25,'Fused logic input',16,'schref');
    s+=wire('VBAT_L','M30 74 H246 M100 74 V105 M200 74 V105',32,61)+pin('F2.1',30,74,'F2.1',0,19);
    s+=strokes('M90 105 L110 105 L100 119 Z M90 133 L110 133 L100 119 Z M89 119 H111 M185 116 H215 M185 123 H215 M200 105 V116 M200 123 V133');
    s+=text(67,122,'D1',12,'schref')+text(218,122,'C1',12,'schref');
    s+=wire('GND','M100 133 V159 H200 V133',118,175,'GND');
    s+=pin('D1.1',100,105,'1',12,-4)+pin('D1.2',100,133,'2',12,12)+pin('C1.1',200,105,'1',12,-4)+pin('C1.2',200,133,'2',12,12);
    s+=text(301,25,'U1 charge-pump capacitor',15,'schref');
    s+=wire('U1_VCAP','M310 75 H391',307,57)+wire('VBAT_L','M419 75 H520',462,57);
    s+=strokes('M391 75 H401 M401 61 V89 M409 61 V89 M409 75 H419');
    s+=pin('U1.1',310,75,'U1.1',0,21)+pin('C2.1',391,75,'1',0,19)+pin('C2.2',419,75,'2',0,19)+pin('U1.6',520,75,'U1.6',0,21)+text(406,110,'C2',13,'schref','middle');
    s+=text(15,215,'Protected supply to regulators',16,'schref');
    s+=wire('VIN','M32 250 H502 M115 250 V287 M200 250 V287 M285 250 V287 M408 250 V270',45,241);
    s+=pin('Q1.5',32,250,'Q1.5',6,19)+pin('TP1.1',502,250,'TP1',0,20);
    s+=wire('GND','M75 365 H456 M115 316 V365 M200 316 V365 M285 316 V365 M408 343 V365',316,382);
    s+=pin('TP2.1',75,365,'TP2',0,20);
    for(const [x,r] of [[115,'C3'],[200,'C4'],[285,'C5']]){
      s+=strokes('M'+x+' 287 v10 m-12 0 h24 m-24 7 h24 m-12 0 v12');
      s+=pin(r+'.1',x,287,r==='C5'?'1':'+1',12,-3)+pin(r+'.2',x,316,'2',12,11)+text(x-17,305,r,12,'schref','end');
    }
    s+=box(400,270,16,21)+pin('R1.1',408,270,'1',14,-2)+pin('R1.2',408,291,'2',14,6)+text(382,288,'R1',12,'schref');
    s+=wire('D2_A','M408 291 V312',427,310)+pin('D2.2',408,312,'2',-12,4);
    s+=strokes('M408 312 v4 M399 316 H417 L408 331 Z M397 332 H419 M408 332 v11 M420 323 l9 -8 m-5 0 h5 v5 M423 331 l9 -8 m-5 0 h5 v5');
    s+=pin('D2.1',408,343,'1',-12,4)+text(379,333,'D2',12,'schref');return s;
  }
  const protectionMarkup=protection();
  const protectionPins=new Set(selectedRefs);
  const wiredPins=new Set([...distributionPins,...protectionPins]);
  function circuitFor(key,preferred){
    if(preferred==='sheet')return 'sheet';
    if(preferred==='protection'&&protectionPins.has(key))return 'protection';
    if(distributionPins.has(key))return 'wired';
    return protectionPins.has(key)?'protection':'sheet';
  }
  right.innerHTML='<rect x="0" y="0" width="228" height="108" rx="2" fill="#f8faf7" stroke="#516d63" stroke-width=".18"/>'+board+'<g id="br-marker"></g>';
  const layerCount = {};
  for(const g of right.querySelectorAll('[data-layer]')){
    const counts={};
    for(const el of g.querySelectorAll('[data-n]')) {const n=el.dataset.n;counts[n]??={pour:0,trace:0,pad:0};counts[n][el.classList[0]]++;}
    layerCount[g.dataset.layer]=counts;
  }
  const pcbRefs=[...right.querySelectorAll('.refs text')];
  const button=(label,action,current=false)=>{
    const b=document.createElement('button'); b.type='button';b.textContent=label;b.classList.toggle('active',current);b.addEventListener('click',action);return b;
  };
  let sheetURLPromise, modeVersion=0;
  function sheetURL(){
    if(!sheetURLPromise)sheetURLPromise=(async()=>{
      const bytes=Uint8Array.from(atob(sheetImage),s=>s.charCodeAt(0));
      const raw=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
      return URL.createObjectURL(new Blob([await new Response(raw).arrayBuffer()],{type:'image/svg+xml'}));
    })();
    return sheetURLPromise;
  }
  function renderLeft(){
    const version=++modeVersion;
    if(state.mode!=='sheet'){
      left.innerHTML=state.mode==='protection'?protectionMarkup:wiredMarkup;view(left,[0,0,550,408]);return;
    }
    left.innerHTML='<image id="br-art" x="0" y="0" width="1189" height="1050" preserveAspectRatio="none"/>'+sheetPins+'<g id="br-sheet-marker"></g>';
    sheetURL().then(url=>{if(version===modeVersion)get('art').setAttribute('href',url);}).catch(()=>{get('note').textContent='Original-sheet artwork requires a browser with gzip decompression support. The full schematic PDF is linked below.';});
    focusSheet(splitPin(state.key)[0]);
  }
  function chooseLayer(){
    const layer=get('layer').value;
    for(const g of right.querySelectorAll('[data-layer]'))g.toggleAttribute('hidden',g.dataset.layer!==layer);
    if(pcbRefs.length)pcbRefs[0].parentElement.style.opacity=layer==='F.Cu'?1:.6;
  }
  function highlight(){
    for(const svg of [left,right]){
      for(const el of svg.querySelectorAll('.on,.current'))el.classList.remove('on','current');
      for(const el of svg.querySelectorAll('[data-n="'+state.n+'"]'))el.classList.add('on');
      for(const el of svg.querySelectorAll('[data-pin="'+CSS.escape(state.key)+'"]'))el.classList.add('current');
    }
    const pd=pinData(state.key);
    const rings=(points,r)=>points.map(([x,y])=>'<circle class="mark" cx="'+x+'" cy="'+y+'" r="'+r+'"/>').join('');
    const keys=owners[state.n].length<=8?owners[state.n]:[state.key];
    const used=[];
    const printPin=(key)=>{
      const pts=pinData(key).b;
      const x=pts.reduce((v,p)=>v+p[0],0)/pts.length,y=pts.reduce((v,p)=>v+p[1],0)/pts.length;
      let yy=y-3.1;while(used.some(p=>Math.abs(x-p[0])<10&&Math.abs(yy-p[1])<2.6))yy-=2.8;
      used.push([x,yy]);return '<g class="padlabel"><path d="M'+x+' '+y+' L'+(x+2)+' '+yy+'" stroke="#45534e" stroke-width=".15"/>'+text(x+2.1,yy,key,1.85)+'</g>';
    };
    get('marker').innerHTML=rings(pd.b,1.15)+keys.map(printPin).join('');
    if(state.mode==='sheet' && pd.s)get('sheet-marker').innerHTML=rings([pd.s],1.2);
  }
  function refresh(){
    const pd=pinData(state.key),[ref,pin]=splitPin(state.key);get('mode').value=state.mode;
    chooseLayer();highlight();
    const list=owners[state.n],stats=layerCount[get('layer').value][state.n]||{pour:0,trace:0,pad:0};
    get('net').textContent=nets[state.n]+'  ·  '+state.key;
    get('value').textContent=detail[ref].value+'   |   '+get('layer').value+'  ·  '+stats.trace+' track segments, '+stats.pour+' filled regions, '+stats.pad+' pads';
    get('partpins').replaceChildren(...Object.entries(detail[ref].pins).map(([num,v])=>option(ref+'.'+num,num+'  '+(v.name&&v.name!=='~'?v.name+'  ':'')+nets[v.n])));
    get('partpins').value=state.key;
    get('count').textContent='Connected pins ('+list.length+')';
    get('ends').replaceChildren(...[...list].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true})).map(key=>button(key,()=>selectPin(key,{focus:true}),key===state.key)));
    get('step').textContent=state.step<0?'Exploring':(state.step+1)+' / '+routes[state.route].length;
    root.querySelector('[data-action="prev"]').disabled=state.step===0;
    root.querySelector('[data-action="next"]').disabled=state.step===routes[state.route].length-1;
    if(state.step>=0)get('note').textContent=routes[state.route][state.step][1];
    else get('note').textContent=state.mode==='sheet'&&!pd.wire?'Single-ended board net. This pin is marked unconnected on the source schematic.':'Follow '+nets[state.n]+' to another connected pin, or choose another pin on '+ref+' to cross that component.';
  }
  function selectPin(key,{focus=false,step=-1,autoLayer=true}={}){
    const pd=pinData(key);if(!pd)return;
    state.key=key;state.n=pd.n;state.step=step;
    const mode=circuitFor(key,state.mode);if(mode!==state.mode){state.mode=mode;renderLeft();}
    if(autoLayer&&right.querySelector('[data-layer="'+get('layer').value+'"] [data-pin="'+CSS.escape(key)+'"]')===null)get('layer').value='F.Cu';
    if(focus)focusPCB(key);
    if(state.mode==='sheet')focusSheet(splitPin(key)[0]);
    refresh();
  }
  function chooseNet(n){
    const ends=owners[n];if(!ends?.length)return;
    const key=ends.includes(state.key)?state.key:ends.find(k=>wiredPins.has(k))||ends[0];selectPin(key,{autoLayer:false});
  }
  function routeStep(i){
    const steps=routes[state.route];i=Math.max(0,Math.min(i,steps.length-1));
    const key=steps[i][0];
    get('layer').value=state.route==='motor'&&i>=4?'In1.Cu':'F.Cu';
    state.mode=circuitFor(key,state.mode);renderLeft();
    view(right,sectionBox);selectPin(key,{step:i});
  }
  function fit(svg){
    view(svg,svg===right?fullBox:state.mode!=='sheet'?[0,0,550,408]:[0,0,1189,1050]);
  }
  function panZoom(svg){
    let drag=null;
    svg.addEventListener('pointerdown',e=>{
      if(e.button!==0)return;
      const p=origin(svg,e);drag={cx:e.clientX,cy:e.clientY,p,box:views.get(svg),target:e.target,id:e.pointerId,moved:false};
      svg.setPointerCapture(e.pointerId);
    });
    svg.addEventListener('pointermove',e=>{
      if(!drag||drag.id!==e.pointerId)return;
      const dx=e.clientX-drag.cx,dy=e.clientY-drag.cy;
      if(Math.hypot(dx,dy)>3)drag.moved=true;
      if(drag.moved){const [x,y,w,h]=drag.box,scale=svg.getScreenCTM().a;view(svg,[x-dx/scale,y-dy/scale,w,h]);}
    });
    svg.addEventListener('pointerup',e=>{
      if(!drag||drag.id!==e.pointerId)return;
      const {target,moved}=drag;drag=null;
      if(moved)return;
      const obj=target.closest('[data-n]');if(!obj || !owners[obj.dataset.n])return;
      if(obj.dataset.pin)selectPin(obj.dataset.pin,{autoLayer:svg===left,focus:svg===left&&state.mode==='sheet'});else chooseNet(obj.dataset.n);
    });
    svg.addEventListener('pointercancel',()=>{drag=null;});
    svg.addEventListener('wheel',e=>{if(e.ctrlKey||e.metaKey){e.preventDefault();zoom(svg,e.deltaY<0?.8:1.25,origin(svg,e));}},{passive:false});
    svg.addEventListener('keydown',e=>{
      const [x,y,w,h]=views.get(svg);const dirs={ArrowUp:[0,-h/8],ArrowDown:[0,h/8],ArrowLeft:[-w/8,0],ArrowRight:[w/8,0]};
      if(dirs[e.key]){e.preventDefault();const [dx,dy]=dirs[e.key];view(svg,[x+dx,y+dy,w,h]);}
      if(['+','=','-'].includes(e.key)){e.preventDefault();zoom(svg,e.key==='-'?1.25:.8);}
    });
  }
  const allKeys=Object.keys(detail).filter(ref=>Object.keys(detail[ref].pins).length);
  const known=new Map([...allKeys,...Object.values(nets).filter(Boolean),...Object.values(owners).flat()].map(v=>[v.toUpperCase(),v]));
  get('choices').replaceChildren(...[...known.values()].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true})).map(k=>option(k,k)));
  root.querySelector('form').addEventListener('submit',e=>{
    e.preventDefault();const input=get('query');const value=known.get(input.value.trim().toUpperCase());
    if(!value){input.setCustomValidity('Choose a reference, connected pin or net from the list.');input.reportValidity();return;}
    const net=netId(value);let key=pinData(value)?value:detail[value]?value+'.'+Object.keys(detail[value].pins)[0]:owners[net]?.[0];
    if(key)selectPin(key,{focus:true});
  });
  get('query').addEventListener('input',()=>get('query').setCustomValidity(''));
  get('partpins').onchange=e=>selectPin(e.target.value,{focus:true});
  get('mode').onchange=e=>{
    state.mode=e.target.value;
    const pinsForMode=state.mode==='wired'?distributionPins:protectionPins;
    if(state.mode!=='sheet'&&!pinsForMode.has(state.key)){state.key=state.mode==='wired'?'J1.2':'D1.1';state.n=pinData(state.key).n;state.step=-1;view(right,sectionBox);}
    renderLeft();refresh();
  };
  function updateDisplay(){
    right.classList.toggle('artwork',get('display').value==='artwork');
    right.classList.toggle('no-fills',!get('fills').checked);
    root.querySelector('.br-key').classList.toggle('plain',get('display').value==='artwork');
  }
  get('display').onchange=updateDisplay;
  get('fills').onchange=updateDisplay;
  function inspectCopper(gate){
    get('display').value='selected';
    get('fills').checked=true;
    updateDisplay();
    state.route=gate?'gate':'motor';
    state.mode='wired';
    get('route').value=state.route;
    routeStep(gate?2:0);
    view(right,gate?[19,56,11,8]:[10,25,30,20]);
  }
  get('layer').onchange=refresh;
  get('route').onchange=e=>{state.route=e.target.value;routeStep(0);};
  const expand=root.querySelector('[data-action="expand"]');
  function toggleExpand(){
    const open=root.classList.toggle('expanded');expand.setAttribute('aria-pressed',open);expand.textContent=open?'Close expanded view':'Expand reader';
    if(!open){root.scrollIntoView({block:'start'});expand.focus({preventScroll:true});}
  }
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&root.classList.contains('expanded'))toggleExpand();});
  root.addEventListener('click',e=>{
    const b=e.target.closest('button[data-action]');if(!b)return;
    const action=b.dataset.action,svg=b.dataset.view==='left'?left:right;
    if(action==='gate-track'||action==='battery')inspectCopper(action==='gate-track');
    else if(action==='expand')toggleExpand();
    else if(action==='fit')fit(svg);
    else if(action==='input'){view(right,sectionBox);}
    else if(action==='prev'||action==='next')routeStep(state.step<0?0:state.step+(action==='prev'?-1:1));
    else if(action==='in'||action==='out')zoom(svg,action==='in'?.7:1/.7);
  });
  function openPinLink(){
    const hash=decodeURIComponent(location.hash.slice(1));
    if(!hash.startsWith('trace-pin-'))return;
    const key=hash.slice(10);
    if(!pinData(key))return;
    state.mode='sheet';renderLeft();selectPin(key,{focus:true});root.scrollIntoView({block:'start'});
  }
  window.addEventListener('hashchange',openPinLink);
  document.addEventListener('click',event=>{
    const link=event.target.closest('a[href^="#trace-pin-"]');
    if(link && link.hash===location.hash)openPinLink();
  });
  panZoom(left);panZoom(right);routeStep(0);openPinLink();
})();
