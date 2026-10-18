'use strict';
// Switch only the recorded explanation. No model, training or evaluation requests.
(() => {
  const tabs=[...document.querySelectorAll('[data-case]')];
  function select(tab,focus=false){
    for(const item of tabs){const active=item===tab;item.setAttribute('aria-selected',String(active));item.tabIndex=active?0:-1;document.getElementById(item.getAttribute('aria-controls')).hidden=!active;}
    if(focus)tab.focus();
  }
  tabs.forEach((tab,index)=>{
    tab.addEventListener('click',()=>select(tab));
    tab.addEventListener('keydown',event=>{
      let next;
      if(event.key==='ArrowRight')next=(index+1)%tabs.length;
      if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;
      if(event.key==='Home')next=0;
      if(event.key==='End')next=tabs.length-1;
      if(next!==undefined){event.preventDefault();select(tabs[next],true);}
    });
  });
  // Existing deep links still open the preserved evidence inside disclosures.
  function revealHash(){
    const target=document.getElementById(location.hash.slice(1));if(!target)return;
    let node=target.parentElement;while(node){if(node.tagName==='DETAILS')node.open=true;node=node.parentElement;}
    requestAnimationFrame(()=>target.scrollIntoView({block:'start',behavior:'instant'}));
  }
  addEventListener('hashchange',revealHash);
  if(location.hash)revealHash();
})();
