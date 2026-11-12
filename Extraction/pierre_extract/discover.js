() => {
 const assets = [];
 const add = (url, el, kind) => {
   if (!url || /^(data:|blob:|javascript:)/i.test(url)) return;
   try { assets.push({url:new URL(url, document.baseURI).href,
     alt:(el?.getAttribute('alt') || el?.getAttribute('title') || '').slice(0,500), kind}); } catch {}
 };
 const srcset = (s,el) => {
   // URLs de srcset usuelles ; les data: sont exclues.
   const entries=(s||'').split(',').map(p=>p.trim().split(/\s+/));
   entries.sort((a,b)=>(parseFloat(b[1])||0)-(parseFloat(a[1])||0));
   for (const part of entries) add(part[0],el,'srcset');
 };
 for (const el of document.querySelectorAll('img,source')) {
   for (const attr of ['src','data-src','data-original','data-lazy-src','data-image','data-large','data-full'])
     add(el.getAttribute(attr),el,attr);
   add(el.currentSrc,el,'currentSrc');
   srcset(el.getAttribute('srcset'),el); srcset(el.getAttribute('data-srcset'),el);
 }
 for (const el of document.querySelectorAll('body *')) {
   for (const pseudo of [null,'::before','::after']) {
     const css=getComputedStyle(el,pseudo).backgroundImage;
     for (const m of css.matchAll(/url\(\s*["']?(.*?)["']?\s*\)/g)) add(m[1],el,'background');
   }
 }
 for (const a of document.querySelectorAll('a[href]'))
   if (/\.(jpe?g|png|webp|avif)(?:[?#]|$)/i.test(a.href)) add(a.href,a,'linked-original');
 for (const m of document.querySelectorAll('meta[property="og:image"],meta[name="twitter:image"]'))
   add(m.content,m,'metadata');
 return {assets, links:[...document.querySelectorAll('a[href]')].map(a=>a.href),
   anchors:[...document.querySelectorAll('a[href]')]
     .map(a=>({t:(a.innerText||'').trim().slice(0,120), h:a.href}))
     .filter(a=>a.h && a.t && !/^(javascript:|mailto:|tel:|data:|#)/i.test(a.h))
     .slice(0,400),
   title:document.title, text:document.body?.innerText.slice(0,150000)||'',
   description:document.querySelector('meta[name="description"]')?.content||''};
}
