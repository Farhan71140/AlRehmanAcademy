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
