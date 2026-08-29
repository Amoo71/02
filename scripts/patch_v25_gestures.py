from pathlib import Path

p = Path("app/src/main/assets/index.html")
s = p.read_text(encoding="utf-8")

# No separate Arrange button: long press on an app enters move mode.
s = s.replace(
    '<button id="systemChip" class="chip sys">System</button><button id="arrangeChip" class="chip arrange">Arrange</button>',
    '<button id="systemChip" class="chip sys">System</button>'
)
s = s.replace(
    '.appsBar{display:grid;grid-template-columns:minmax(0,1fr) auto auto auto;gap:7px}',
    '.appsBar{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:7px}'
)
s = s.replace(
    '@media(max-width:380px){.appGrid{grid-template-columns:repeat(3,minmax(0,1fr))}.appsBar{grid-template-columns:minmax(0,1fr) auto auto}',
    '@media(max-width:380px){.appGrid{grid-template-columns:repeat(3,minmax(0,1fr))}.appsBar{grid-template-columns:minmax(0,1fr) auto}'
)

# Settings are opened by double tap, so the ellipsis is no longer needed.
s = s.replace('.tile.arrangeMode .more{display:none}', '.more{display:none}.tile.arrangeMode .more{display:none}')
s = s.replace('</style>', '.tile{-webkit-user-select:none;user-select:none}.tile.arrangeMode{animation:appWiggle .18s ease-in-out infinite alternate}@keyframes appWiggle{from{transform:rotate(-.5deg)}to{transform:rotate(.5deg)}}\n</style>', 1)

old_listeners = "$('systemChip').onclick=()=>{S.system=!S.system;S.page=0;$('systemChip').classList.toggle('on',S.system);renderApps()};$('arrangeChip').onclick=()=>{S.arrange=!S.arrange;S.selectedArrange=null;$('arrangeChip').classList.toggle('on',S.arrange);toast(S.arrange?'Tap two apps to swap':'Arrangement saved');renderApps()};document.querySelectorAll('[data-theme]').forEach(b=>b.onclick=()=>setTheme(b.dataset.theme));$('prevPage').onclick"
new_listeners = "$('systemChip').onclick=()=>{S.system=!S.system;S.page=0;$('systemChip').classList.toggle('on',S.system);renderApps()};document.querySelectorAll('[data-theme]').forEach(b=>b.onclick=()=>setTheme(b.dataset.theme));$('prevPage').onclick"
if old_listeners not in s:
    raise SystemExit('v2.5 arrange listener block not found')
s = s.replace(old_listeners, new_listeners, 1)

old_grid = "$('appGrid').onclick=e=>{const more=e.target.closest('[data-more]');if(more&&!S.arrange){e.stopPropagation();openSheet(more.dataset.more);return}const tile=e.target.closest('[data-open]');if(!tile)return;const pkg=tile.dataset.open;if(S.arrange){if(!S.selectedArrange){S.selectedArrange=pkg;renderApps();return}if(S.selectedArrange===pkg){S.selectedArrange=null;renderApps();return}ensureOrder();const a=S.order.indexOf(S.selectedArrange),b=S.order.indexOf(pkg);if(a>=0&&b>=0){const tmp=S.order[a];S.order[a]=S.order[b];S.order[b]=tmp;persistOrder()}S.selectedArrange=null;renderApps();return}const app=findApp(pkg);if(S.showHidden)openSheet(pkg);else if(app&&app.launchable)action('launch',pkg);else openSheet(pkg)};"
new_grid = r'''let appTapTimer=null;
let appTapPackage=null;
let appTapAt=0;
let appLongTimer=null;
let appLongTriggered=false;

function finishMove(targetPkg){
  if(!S.selectedArrange){S.arrange=false;renderApps();return}
  ensureOrder();
  const a=S.order.indexOf(S.selectedArrange);
  const b=S.order.indexOf(targetPkg);
  if(a>=0&&b>=0&&a!==b){
    const tmp=S.order[a];
    S.order[a]=S.order[b];
    S.order[b]=tmp;
    persistOrder();
    toast('Position saved');
  }
  S.arrange=false;
  S.selectedArrange=null;
  renderApps();
}

$('appGrid').addEventListener('pointerdown',e=>{
  const tile=e.target.closest('[data-open]');
  if(!tile)return;
  const pkg=tile.dataset.open;
  appLongTriggered=false;
  clearTimeout(appLongTimer);
  appLongTimer=setTimeout(()=>{
    appLongTriggered=true;
    clearTimeout(appTapTimer);
    appTapTimer=null;
    appTapPackage=null;
    S.arrange=true;
    S.selectedArrange=pkg;
    renderApps();
    toast('Move app · tap destination');
  },520);
});

['pointerup','pointercancel','pointerleave'].forEach(ev=>
  $('appGrid').addEventListener(ev,()=>clearTimeout(appLongTimer))
);

$('appGrid').onclick=e=>{
  const tile=e.target.closest('[data-open]');
  if(!tile)return;
  const pkg=tile.dataset.open;

  if(appLongTriggered){
    appLongTriggered=false;
    return;
  }

  if(S.arrange){
    finishMove(pkg);
    return;
  }

  const now=Date.now();
  if(appTapPackage===pkg && now-appTapAt<340){
    clearTimeout(appTapTimer);
    appTapTimer=null;
    appTapPackage=null;
    appTapAt=0;
    openSheet(pkg);
    return;
  }

  clearTimeout(appTapTimer);
  appTapPackage=pkg;
  appTapAt=now;
  appTapTimer=setTimeout(()=>{
    appTapTimer=null;
    appTapPackage=null;
    const app=findApp(pkg);
    if(app&&app.launchable) action('launch',pkg);
    else openSheet(pkg);
  },260);
};'''
if old_grid not in s:
    raise SystemExit('v2.5 app grid handler not found')
s = s.replace(old_grid, new_grid, 1)

p.write_text(s, encoding="utf-8")
