const nav=document.getElementById('nav'),bg=document.querySelector('[data-parallax]');
const on=()=>{nav.classList.toggle('s',scrollY>40);if(bg&&scrollY<innerHeight)bg.style.transform=`translate3d(0,${scrollY*.25}px,0) scale(1.08)`};
addEventListener('scroll',()=>requestAnimationFrame(on),{passive:true});on();
const b=document.querySelector('.burger');b.addEventListener('click',()=>{const o=nav.classList.toggle('open');b.setAttribute('aria-expanded',o)});
const io=new IntersectionObserver(e=>e.forEach(x=>{if(x.isIntersecting){x.target.classList.add('on');io.unobserve(x.target)}}),{threshold:.12});
document.querySelectorAll('.rv,.reveal-img').forEach(e=>io.observe(e));
