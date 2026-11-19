const nav=document.getElementById('nav'),bg=document.querySelector('[data-parallax]');
const wide=matchMedia('(min-width:900px)'),still=matchMedia('(prefers-reduced-motion:reduce)');
const on=()=>{nav.classList.toggle('s',scrollY>40);
  if(bg&&wide.matches&&!still.matches&&scrollY<innerHeight)bg.style.transform=`translate3d(0,${scrollY*.25}px,0) scale(1.08)`};
addEventListener('scroll',()=>requestAnimationFrame(on),{passive:true});on();

/* menu (phones + tablets) */
const b=document.querySelector('.burger');
const setMenu=o=>{nav.classList.toggle('open',o);if(b)b.setAttribute('aria-expanded',o)};
if(b)b.addEventListener('click',()=>setMenu(!nav.classList.contains('open')));
nav.querySelectorAll('.links a').forEach(a=>a.addEventListener('click',()=>{if(!a.matches('.dd > a')||innerWidth>1100)setMenu(false)}));
addEventListener('keydown',e=>{if(e.key==='Escape')setMenu(false)});
addEventListener('resize',()=>{if(innerWidth>1100)setMenu(false)});

/* touch laptops/tablets in desktop layout: 1st tap opens Courses dropdown, 2nd tap follows link */
const dd=nav.querySelector('.dd');
if(dd){dd.firstElementChild.addEventListener('click',e=>{
  if(innerWidth>1100&&matchMedia('(hover:none)').matches&&!dd.classList.contains('open')){e.preventDefault();dd.classList.add('open')}});
  document.addEventListener('click',e=>{if(!dd.contains(e.target))dd.classList.remove('open')})}

/* scroll reveal
   Uses getBoundingClientRect instead of IntersectionObserver: Chrome/Edge on desktop treat an element hidden by
   clip-path (the .reveal-img images) as "not visible", so the observer never fired and those images stayed hidden. */
const els=[...document.querySelectorAll('.rv,.reveal-img')];
let pending=els.slice(),queued=false;
const reveal=()=>{queued=false;const h=innerHeight;
  pending=pending.filter(e=>{const r=e.getBoundingClientRect();if(r.top<h*.92&&r.bottom>0){e.classList.add('on');return false}return true})};
const queue=()=>{if(!queued&&pending.length){queued=true;requestAnimationFrame(reveal)}};
addEventListener('scroll',queue,{passive:true});addEventListener('resize',queue);addEventListener('load',queue);
reveal();
setTimeout(()=>{pending.forEach(e=>{if(e.getBoundingClientRect().top<innerHeight*2)e.classList.add('on')})},4000); // safety net

/* donation: amount chips (USD), payment link or WhatsApp, copy buttons */
(()=>{const g=document.getElementById('donate');if(!g)return;
 const chips=g.querySelectorAll('.chip'),amt=g.querySelector('#d-amt'),cause=g.querySelector('#d-cause'),go=g.querySelector('#d-go'),hint=g.querySelector('#d-hint');
 chips.forEach(c=>c.addEventListener('click',()=>{chips.forEach(x=>x.classList.remove('sel'));c.classList.add('sel');amt.value=c.dataset.v}));
 amt.addEventListener('input',()=>chips.forEach(x=>x.classList.toggle('sel',x.dataset.v===amt.value)));
 if(go)go.addEventListener('click',()=>{const a=Math.round(parseFloat(amt.value)*100)/100;
   if(!(a>=1)){hint.textContent='Please choose or enter an amount first (minimum $1).';amt.focus();return}
   const link=(g.dataset.link||'').trim();
   if(/^https:\/\//i.test(link)){
     window.open(link.replace('{amount}',a),'_blank','noopener');
     hint.textContent='Opening our payment page. Please mention "'+cause.value+'" in the note if there is one.';
   }else{
     const t='Assalamu Alaikum, I would like to donate $'+a+' towards: '+cause.value+'. Please share the payment details.';
     window.open('https://wa.me/923192788158?text='+encodeURIComponent(t),'_blank','noopener');
     hint.textContent='Opening WhatsApp so we can send you the payment details.';
   }});
 g.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{
   try{await navigator.clipboard.writeText(b.dataset.copy);const t=b.textContent;b.textContent='Copied';setTimeout(()=>b.textContent=t,1500)}catch(e){}}));
})();

/* nav search (live results) + contact/account popover */
(()=>{const sBtn=document.getElementById('sbtn'),sp=document.getElementById('sp'),back=document.getElementById('sback'),
 cBtn=document.getElementById('cbtn'),cp=document.getElementById('cpop');
 if(!sBtn||!sp)return;
 const inp=document.getElementById('sq'),res=document.getElementById('sres'),hint=document.getElementById('shint'),chips=document.getElementById('schips'),
  form=inp.form,xb=document.getElementById('sx');
 let timer,ctrl,act=-1;
 const setS=o=>{sp.classList.toggle('on',o);back.classList.toggle('on',o);sp.setAttribute('aria-hidden',String(!o));sBtn.setAttribute('aria-expanded',String(o));
  if(o){setC(false);setMenu(false);setTimeout(()=>inp.focus(),80)}};
 const setC=o=>{if(!cp)return;cp.classList.toggle('on',o);cp.setAttribute('aria-hidden',String(!o));cBtn.setAttribute('aria-expanded',String(o));
  if(o){setS(false);setMenu(false)}};
 const hl=(el,t,q)=>{const i=t.toLowerCase().indexOf(q.toLowerCase());
  if(i<0){el.textContent=t;return}
  const m=document.createElement('mark');m.textContent=t.slice(i,i+q.length);el.append(t.slice(0,i),m,t.slice(i+q.length))};
 const render=(items,q)=>{res.textContent='';act=-1;
  items.forEach(it=>{const a=document.createElement('a');a.className='s-item';a.href=it.url;a.setAttribute('role','option');
   const c=document.createElement('span'),n=document.createElement('span'),d=document.createElement('span');
   c.className='c';c.textContent=it.cat;n.className='n';hl(n,it.name,q);d.className='d';d.textContent=it.duration;
   a.append(c,n,d);res.append(a)});
  const t=document.createElement(items.length?'a':'p');
  if(items.length){t.className='s-all';t.href=form.action+'?q='+encodeURIComponent(q);t.textContent='View all results \u2192'}
  else{t.className='s-none';t.textContent='No courses match \u201C'+q+'\u201D. Try another word.'}
  res.append(t)};
 const run=()=>{const q=inp.value.trim(),empty=q.length<2;
  hint.hidden=chips.hidden=!empty;clearTimeout(timer);
  if(empty){res.textContent='';return}
  timer=setTimeout(async()=>{ctrl&&ctrl.abort();ctrl=new AbortController();
   try{const r=await fetch(sp.dataset.api+'?q='+encodeURIComponent(q),{signal:ctrl.signal});const j=await r.json();
    if(inp.value.trim()===q)render(j.results||[],q)}catch(e){}},170)};
 inp.addEventListener('input',run);
 inp.addEventListener('keydown',e=>{const it=[...res.querySelectorAll('.s-item')];
  if((e.key==='ArrowDown'||e.key==='ArrowUp')&&it.length){e.preventDefault();
   act=e.key==='ArrowDown'?(act+1)%it.length:(act<=0?it.length-1:act-1);
   it.forEach((x,i)=>x.classList.toggle('act',i===act));it[act].scrollIntoView({block:'nearest'})}
  else if(e.key==='Enter'&&act>=0&&it[act]){e.preventDefault();location.href=it[act].href}});
 sBtn.addEventListener('click',()=>setS(!sp.classList.contains('on')));
 xb.addEventListener('click',()=>setS(false));back.addEventListener('click',()=>{setS(false);setC(false)});
 if(cBtn)cBtn.addEventListener('click',e=>{e.stopPropagation();setC(!cp.classList.contains('on'))});
 document.addEventListener('click',e=>{if(cp&&cp.classList.contains('on')&&!cp.contains(e.target)&&!cBtn.contains(e.target))setC(false)});
 if(b)b.addEventListener('click',()=>{setS(false);setC(false)});
 addEventListener('keydown',e=>{
  if(e.key==='Escape'){setS(false);setC(false)}
  else if((e.key==='/'&&!/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName))||((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k')){e.preventDefault();setS(true)}});
})();
