"""PriDialog: the one in-app replacement for alert() and confirm().

A native dialog cannot be styled, announces itself as "localhost says" or "the page
at ... says", and in the Kit it sat on top of a page the working group is asked to
judge. Q-27 replaced both; UI Elements deviation PDT-37 lists the eight call sites.

The strings live here, in their own module, rather than inside build_site.py, because
the Data Console needs the same dialog and importing build_site.py would run a whole
site build. build_site.py bakes them into the Kit; admin_server.py stamps them into
admin_ui.html. One definition, two surfaces.

Built properly from the start so it does not become another PDT-34: role, aria-modal,
a label, focus moved in and handed back, Escape to cancel, and Tab kept inside.

Pure stdlib (no imports at all).

    PriDialog.confirm({title, message, okLabel, cancelLabel, danger}) -> Promise<boolean>
    PriDialog.notify({title, message, okLabel})                       -> Promise<void>

The names follow docs/design.md section 4. `danger` gives the main action the navy
button rather than the orange one. ask() is not built: the spec notes this app has
no prompt() to replace, so it waits for a caller.

The compact card keeps its own .pdlg classes rather than the public modal shell,
because merging the two shells is PDT-04 and waits on Q-14.
"""

DIALOG_CSS = """
.pdlg{position:fixed;inset:0;background:rgba(19,41,75,.55);display:flex;align-items:center;
  justify-content:center;padding:5vh 16px;z-index:10000}
.pdlg-card{background:#fff;border-radius:12px;max-width:440px;width:100%;padding:22px 24px;
  box-shadow:0 18px 50px rgba(0,0,0,.25)}
.pdlg-t{margin:0 0 8px;font-size:18px;line-height:1.3;color:#13294B}
.pdlg-b{margin:0 0 18px;font-size:14.5px;line-height:1.5;color:#23272C}
.pdlg-acts{display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap}
.notice{border-radius:8px;padding:10px 14px;font-size:13.5px;line-height:1.45;margin:10px 0}
.notice.ok{background:#E8F5EC;border:1px solid #B7DFC4;color:#14532D}
.notice.warn{background:#FFF8EF;border:1px solid #F2D9B3;color:#7A5312}
.notice.err{background:#FDECEA;border:1px solid #F5C2BC;color:#7F1D1D}
.notice[hidden]{display:none}
"""

DIALOG_JS = """
var PriDialog=(function(){
  function show(o,withCancel){
    return new Promise(function(resolve){
      var opener=document.activeElement;
      var id='pdlg'+Math.random().toString(36).slice(2,8);
      var wrap=document.createElement('div');
      wrap.className='pdlg';wrap.setAttribute('role','dialog');
      wrap.setAttribute('aria-modal','true');wrap.setAttribute('aria-labelledby',id);
      var card=document.createElement('div');card.className='pdlg-card';
      var h=document.createElement('h2');h.className='pdlg-t';h.id=id;h.textContent=o.title||'';
      var b=document.createElement('p');b.className='pdlg-b';b.textContent=o.message||'';
      var acts=document.createElement('div');acts.className='pdlg-acts';
      var no=null;
      if(withCancel){no=document.createElement('button');no.type='button';no.className='btn gh';
        no.textContent=o.cancelLabel||'Cancel';acts.appendChild(no);}
      var yes=document.createElement('button');yes.type='button';
      yes.className=o.danger?'btn dk':'btn pri';
      yes.textContent=o.okLabel||'OK';acts.appendChild(yes);
      card.appendChild(h);card.appendChild(b);card.appendChild(acts);wrap.appendChild(card);
      document.body.appendChild(wrap);
      function done(v){
        document.removeEventListener('keydown',key,true);
        if(wrap.parentNode)wrap.parentNode.removeChild(wrap);
        if(opener&&opener.focus){try{opener.focus();}catch(e){}}
        resolve(v);
      }
      function key(e){
        if(e.key==='Escape'){e.preventDefault();done(false);return;}
        if(e.key!=='Tab')return;
        var f=no?[no,yes]:[yes];
        var i=f.indexOf(document.activeElement);
        e.preventDefault();
        f[(i+(e.shiftKey?-1:1)+f.length)%f.length].focus();
      }
      yes.addEventListener('click',function(){done(true);});
      if(no)no.addEventListener('click',function(){done(false);});
      wrap.addEventListener('click',function(e){if(e.target===wrap)done(false);});
      document.addEventListener('keydown',key,true);
      (no||yes).focus();
    });
  }
  return {
    confirm:function(o){return show(o||{},true);},
    notify:function(o){return show(o||{},false).then(function(){});}
  };
})();
"""
