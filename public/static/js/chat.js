/* Al Rehman Islamic Academy: chat assistant widget.
   Talks to /api/chat on this same site, so the Groq key stays on the server. */
(()=>{
const csrf=(document.querySelector('meta[name="csrf"]')||{}).content||'';
const css=`
#ar-chat{position:fixed;left:20px;bottom:20px;z-index:9998;font-family:'Manrope',system-ui,sans-serif;color:#F3EEDF}
#ar-chat *{box-sizing:border-box}
#ar-chat button{font-family:inherit;cursor:pointer}
.ar-t{display:flex;align-items:center;gap:9px;padding:12px 18px;background:#0B2B25;color:#F3EEDF;border:1px solid rgba(212,177,95,.6);font-size:12px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;box-shadow:0 8px 24px rgba(0,0,0,.35);transition:background .2s}
.ar-t:hover{background:#12392F}
.ar-t svg{width:18px;height:18px;fill:none;stroke:#D4B15F;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.ar-p{display:none;position:absolute;left:0;bottom:60px;width:min(380px,calc(100vw - 40px));height:min(540px,calc(100dvh - 130px));flex-direction:column;background:#071F1B;border:1px solid rgba(212,177,95,.4);box-shadow:0 24px 60px rgba(0,0,0,.5)}
.ar-p.on{display:flex}
.ar-h{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border-bottom:1px solid rgba(212,177,95,.22)}
.ar-h b{display:block;font-size:15px;font-weight:600}
.ar-h small{display:block;margin-top:2px;font-size:12px;opacity:.65}
.ar-x{background:none;border:0;color:#F3EEDF;font-size:22px;line-height:1;padding:4px 8px;opacity:.7}
.ar-x:hover{opacity:1}
.ar-m{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px}
.ar-b{max-width:88%;padding:10px 13px;font-size:14px;line-height:1.55;white-space:pre-wrap;overflow-wrap:anywhere}
.ar-b.bot{align-self:flex-start;background:rgba(255,255,255,.07)}
.ar-b.me{align-self:flex-end;background:#D4B15F;color:#0A1F1B}
.ar-b a{color:#E8C877;text-decoration:underline;text-underline-offset:2px}
.ar-b.err{color:#F0B8A8}
.ar-dots{display:inline-flex;gap:4px;padding:4px 0}
.ar-dots i{width:6px;height:6px;border-radius:50%;background:#D4B15F;opacity:.4;animation:arDot 1.1s infinite}
.ar-dots i:nth-child(2){animation-delay:.18s}
.ar-dots i:nth-child(3){animation-delay:.36s}
@keyframes arDot{0%,80%,100%{opacity:.25}40%{opacity:1}}
.ar-s{display:flex;flex-wrap:wrap;gap:8px;padding:0 14px 12px}
.ar-s button{background:none;border:1px solid rgba(212,177,95,.45);color:#E8C877;padding:7px 11px;font-size:12px}
.ar-s button:hover{background:rgba(212,177,95,.12)}
.ar-f{display:flex;border-top:1px solid rgba(212,177,95,.22)}
.ar-f input{flex:1;min-width:0;background:transparent;border:0;outline:0;color:#F3EEDF;padding:15px 16px;font-family:inherit;font-size:16px}
.ar-f input::placeholder{color:rgba(243,238,223,.45)}
.ar-f button{background:#D4B15F;color:#0A1F1B;border:0;padding:0 18px;font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.ar-f button:disabled{opacity:.5;cursor:default}
@media (prefers-reduced-motion:reduce){.ar-dots i{animation:none;opacity:.7}}
`;
const st=document.createElement('style');st.textContent=css;document.head.append(st);

const root=document.createElement('div');root.id='ar-chat';
root.innerHTML=`<button class="ar-t" type="button" aria-expanded="false" aria-controls="ar-p"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.5-4.6A8 8 0 1 1 21 12z"/></svg><span>Ask us</span></button>
<div class="ar-p" id="ar-p" role="dialog" aria-label="Chat assistant"><div class="ar-h"><div><b>Al Rehman Assistant</b><small>Courses, admissions and donations</small></div><button class="ar-x" type="button" aria-label="Close chat">&times;</button></div>
<div class="ar-m" aria-live="polite"></div><div class="ar-s"></div>
<form class="ar-f"><input type="text" maxlength="500" placeholder="Type your question" aria-label="Your message" autocomplete="off"><button type="submit">Send</button></form></div>`;

const tog=root.querySelector('.ar-t'),panel=root.querySelector('.ar-p'),msgs=root.querySelector('.ar-m'),sugg=root.querySelector('.ar-s'),
 form=root.querySelector('.ar-f'),inp=form.querySelector('input'),sendBtn=form.querySelector('button'),closeBtn=root.querySelector('.ar-x');
const hist=[];let busy=false,greeted=false;

/* plain text + safe same-site links written as [text](/path) */
function render(el,t){el.textContent='';t=t.replace(/\*\*/g,'');
  const re=/\[([^\]]+)\]\((\/[^)\s]*)\)/g;let i=0,x;
  while((x=re.exec(t))){el.append(t.slice(i,x.index));const a=document.createElement('a');a.href=x[2];a.textContent=x[1];el.append(a);i=re.lastIndex}
  el.append(t.slice(i))}
function add(role,text){const d=document.createElement('div');d.className='ar-b '+role;render(d,text);msgs.append(d);msgs.scrollTop=msgs.scrollHeight;return d}

async function send(text){text=(text||'').trim();if(!text||busy)return;
  busy=true;sendBtn.disabled=true;sugg.textContent='';
  add('me',text);hist.push({role:'user',content:text});inp.value='';
  const w=document.createElement('div');w.className='ar-b bot';w.innerHTML='<span class="ar-dots"><i></i><i></i><i></i></span>';
  msgs.append(w);msgs.scrollTop=msgs.scrollHeight;
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({messages:hist.slice(-10)})});
    const j=await r.json().catch(()=>({}));
    if(r.ok&&j.reply){hist.push({role:'assistant',content:j.reply});render(w,j.reply)}
    else{hist.pop();w.classList.add('err');render(w,j.error||'Something went wrong. Please try again, or message us on WhatsApp.')}
  }catch(e){hist.pop();w.classList.add('err');render(w,'Could not reach the assistant. Please try again, or message us on WhatsApp.')}
  busy=false;sendBtn.disabled=false;msgs.scrollTop=msgs.scrollHeight;inp.focus()}

const setOpen=o=>{panel.classList.toggle('on',o);tog.setAttribute('aria-expanded',String(o));
  if(o){
    if(!greeted){greeted=true;
      add('bot','Assalamu Alaikum! I can help you find a course, explain how admissions work, or guide you on donating. What would you like to know?');
      ['Courses for kids','How do I apply?','How can I donate?'].forEach(t=>{const b=document.createElement('button');b.type='button';b.textContent=t;b.onclick=()=>send(t);sugg.append(b)})}
    setTimeout(()=>inp.focus(),60)}};

tog.onclick=()=>setOpen(!panel.classList.contains('on'));
closeBtn.onclick=()=>setOpen(false);
form.onsubmit=e=>{e.preventDefault();send(inp.value)};
addEventListener('keydown',e=>{if(e.key==='Escape'&&panel.classList.contains('on'))setOpen(false)});
document.body.append(root);
})();
