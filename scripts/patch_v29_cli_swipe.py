from pathlib import Path

p = Path("app/src/main/assets/index.html")
s = p.read_text(encoding="utf-8")

# Header: remove decorative square and use compact terminal title.
s = s.replace('<div class="orb"></div>', '')
s = s.replace('<h1>Fire Control</h1>', '<h1>FIRE_CONTROL</h1>')

# Remote section: button/swipe modes, with common lower controls.
old_remote = '<section id="remoteView" class="view"><div class="glass remoteView"><div class="sectionTitle">Remote</div><div class="remoteGrid"><div class="dpadPanel"><div class="dpad"><span></span><button class="rbtn" data-key="up">▲</button><span></span><button class="rbtn" data-key="left">◀</button><button class="rbtn ok" data-key="ok">OK</button><button class="rbtn" data-key="right">▶</button><span></span><button class="rbtn" data-key="down">▼</button><span></span></div><div class="utilityRow"><button class="rbtn" data-key="back">Back</button><button class="rbtn" data-key="home">Home</button><button class="rbtn" data-key="menu">Menu</button></div><div class="volumeRow"><button class="rbtn" data-key="voldown">VOL −</button><button class="rbtn mute" data-key="mute">MUTE</button><button class="rbtn" data-key="volup">VOL +</button></div></div></div></div></section>'
new_remote = '<section id="remoteView" class="view"><div class="glass remoteView"><div class="remoteHead"><div class="sectionTitle">[REMOTE]</div><button id="remoteModeBtn" class="modeBtn" type="button">SWIPE</button></div><div class="remoteGrid"><div class="dpadPanel"><div class="remoteMain"><div id="dpad" class="dpad"><span></span><button class="rbtn" data-key="up">↑</button><span></span><button class="rbtn" data-key="left">←</button><button class="rbtn ok" data-key="ok">OK</button><button class="rbtn" data-key="right">→</button><span></span><button class="rbtn" data-key="down">↓</button><span></span></div><div id="swipePad" class="swipePad"><div class="swipeAscii"><span>↑</span><div><span>←</span><b>+</b><span>→</span></div><span>↓</span></div><div class="swipeHint">SWIPE // TAP = OK</div></div></div><div class="utilityRow"><button class="rbtn" data-key="back">BACK</button><button class="rbtn" data-key="home">HOME</button><button class="rbtn" data-key="menu">MENU</button></div><div class="volumeRow"><button class="rbtn" data-key="voldown">VOL−</button><button class="rbtn mute" data-key="mute">MUTE</button><button class="rbtn" data-key="volup">VOL+</button></div></div></div></div></section>'
if old_remote not in s:
    raise SystemExit("v2.9 remote section marker not found")
s = s.replace(old_remote, new_remote, 1)

# CLI labels and copy.
s = s.replace('<div class="sectionTitle">Tools</div>', '<div class="sectionTitle">[TOOLS]</div>')
s = s.replace('placeholder="Search apps…"', 'placeholder="> search apps..."')
s = s.replace('<span class="themeLabel">Theme</span>', '<span class="themeLabel">THEME</span>')
s = s.replace('>Dark</button>', '>DARK</button>')
s = s.replace('>Pink</button>', '>PINK</button>')
s = s.replace('<b>▦</b>Apps', '<b>[ ]</b>APPS')
s = s.replace('<b>✣</b>Remote', '<b>+--</b>REMOTE')
s = s.replace('<b>⌁</b>Tools', '<b>&gt;_</b>TOOLS')

# Add overriding v2.9 styles just before </style>.
css = r'''

/* v2.9 modern CLI UI ----------------------------------------------------- */
:root{
  --cli-accent:#7cff9b;
  --cli-accent-soft:#7cff9b22;
  --cli-accent-mid:#7cff9b55;
  --cli-bg:#020403;
  --cli-panel:#060908ed;
  --cli-panel2:#0a0e0c;
  --cli-line:#7cff9b25;
  --cli-text:#eaf9ee;
  --cli-muted:#708078;
}
body{
  font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;
  background:radial-gradient(circle at 50% -20%,#102219 0,#050806 34%,#010201 78%);
  color:var(--cli-text);
}
.header{padding:0 3px}.brand{gap:0}.brand h1{font-size:18px;letter-spacing:.015em;font-weight:800}.brand h1::before{content:"> ";color:var(--cli-accent)}.host{color:var(--cli-muted);font-size:10px}.state{border-radius:8px;border-color:var(--cli-line);background:#060a08;color:var(--cli-accent);font-size:10px;padding:7px 9px}.state::before{content:"● ";font-size:8px}.glass{border-radius:13px;border-color:var(--cli-line);background:linear-gradient(180deg,#080b09f2,#030504f2);box-shadow:0 18px 60px #000b,inset 0 1px #ffffff05;backdrop-filter:blur(22px)}
.sectionTitle{color:var(--cli-accent);font-size:10px;letter-spacing:.08em;font-weight:800}.nav{border-radius:12px;border-color:var(--cli-line);background:#040705f2;padding:5px;gap:5px}.navBtn{border-radius:8px;color:var(--cli-muted);font-size:9px;letter-spacing:.05em}.navBtn b{font-size:11px;line-height:15px;font-weight:700}.navBtn.sel{background:var(--cli-accent-soft);color:var(--cli-accent);box-shadow:inset 0 0 0 1px var(--cli-accent-mid),0 7px 20px #0008}.search,.chip,.pageBtn,.rbtn,.toolBtn,.timerChoice,.themeBtn,.sheetBtn,.wake{border-radius:8px;border-color:var(--cli-line);background:#070a08;color:var(--cli-text);box-shadow:none}.search{font-family:inherit}.search:focus{border-color:var(--cli-accent-mid);box-shadow:0 0 0 2px var(--cli-accent-soft)}.chip.on,.themeBtn.on,.rbtn.ok{background:var(--cli-accent);color:#041006;border-color:var(--cli-accent)}.tile{border-radius:10px;border-color:#7cff9b16;background:linear-gradient(145deg,#090d0a,#030504 74%);box-shadow:inset 0 1px #ffffff05}.tile:active{background:var(--cli-accent-soft)}.iconBox{border-radius:9px;background:#0a0e0b;box-shadow:0 7px 18px #0009,inset 0 0 0 1px var(--cli-line)}.tileName{font-size:9px;letter-spacing:-.02em}.pager{color:var(--cli-muted)}.pageInfo{color:var(--cli-muted);font-size:9px}.pageBtn{font-size:14px}.dpadPanel,.timerCard,.themeCard{border-radius:10px;border-color:var(--cli-line);background:#030604}.rbtn{background:linear-gradient(#0a0e0b,#050806);font-size:17px}.rbtn:active{background:var(--cli-accent-soft);color:var(--cli-accent)}.utilityRow .rbtn,.volumeRow .rbtn{font-size:9px;letter-spacing:.04em}.mute{color:#ff8f9a}.toolBtn{background:linear-gradient(145deg,#0a0e0b,#040604);font-size:10px;letter-spacing:.02em}.toolBtn span{color:var(--cli-muted);font-size:8px}.timerTitle,.themeLabel{color:var(--cli-accent);font-size:9px}.timerState{color:var(--cli-muted)}.timerChoice.cancel,.toolBtn.danger{background:#120708;color:#ff8f9a;border-color:#ff8f9a33}.sheet{background:#050806f5;border-color:var(--cli-line);border-radius:12px 12px 0 0}.sheetPkg{color:var(--cli-muted)}.toast{border-radius:7px;border-color:var(--cli-line);background:#07100bdd;color:var(--cli-accent)}

.remoteView{grid-template-rows:28px minmax(0,1fr);gap:5px}.remoteHead{display:flex;align-items:center;justify-content:space-between;min-width:0}.modeBtn{height:25px;min-width:54px;padding:0 8px;border:1px solid var(--cli-line);border-radius:7px;background:#050806;color:var(--cli-accent);font-family:inherit;font-size:8px;font-weight:800;letter-spacing:.05em}.modeBtn::before{content:"["}.modeBtn::after{content:"]"}.remoteGrid{height:100%}.dpadPanel{grid-template-rows:minmax(0,1fr) 40px 40px;padding:7px}.remoteMain{min-height:0;display:grid;place-items:center;overflow:hidden}.dpad{width:min(100%,350px)}.swipePad{display:none;width:min(100%,440px);height:100%;min-height:180px;border:1px solid var(--cli-line);border-radius:10px;background:radial-gradient(circle at 50% 45%,var(--cli-accent-soft),#020403 62%);position:relative;overflow:hidden;touch-action:none;user-select:none;-webkit-user-select:none;place-items:center}.swipePad.on{display:grid}.dpad.off{display:none}.swipePad::before{content:"";position:absolute;inset:8px;border:1px dashed var(--cli-line);border-radius:7px;pointer-events:none}.swipeAscii{width:150px;height:150px;display:grid;grid-template-rows:1fr 1fr 1fr;place-items:center;color:var(--cli-accent);font-size:28px;opacity:.72}.swipeAscii>div{width:100%;display:grid;grid-template-columns:1fr 1fr 1fr;place-items:center}.swipeAscii b{font-weight:400;color:var(--cli-text);font-size:20px}.swipeHint{position:absolute;bottom:15px;font-size:8px;color:var(--cli-muted);letter-spacing:.08em}.swipePad.active{border-color:var(--cli-accent-mid);box-shadow:inset 0 0 35px var(--cli-accent-soft)}

/* Pink uses the exact same CLI layout, only terminal palette changes. */
body.pinkTheme{
  --cli-accent:#ff79c6;
  --cli-accent-soft:#ff79c622;
  --cli-accent-mid:#ff79c65c;
  --cli-bg:#050105;
  --cli-panel:#0c050aed;
  --cli-panel2:#120812;
  --cli-line:#ff79c62b;
  --cli-text:#fff0fa;
  --cli-muted:#a97898;
  --panel:#0c050aed;
  --panel2:#120812;
  --line:#ff79c62b;
  --text:#fff0fa;
  --muted:#a97898;
  background:radial-gradient(circle at 50% -20%,#321020 0,#12060e 34%,#030103 80%);
}
body.pinkTheme .glass,body.pinkTheme .nav,body.pinkTheme .dpadPanel,body.pinkTheme .timerCard,body.pinkTheme .themeCard{background:linear-gradient(180deg,#120811f2,#070306f2);border-color:var(--cli-line)}body.pinkTheme .tile{background:linear-gradient(145deg,#160a13,#070306 74%);border-color:#ff79c618}body.pinkTheme .iconBox{background:#180b15;box-shadow:0 7px 18px #0009,inset 0 0 0 1px var(--cli-line)}body.pinkTheme .rbtn,body.pinkTheme .toolBtn,body.pinkTheme .timerChoice,body.pinkTheme .themeBtn,body.pinkTheme .search,body.pinkTheme .chip,body.pinkTheme .pageBtn,body.pinkTheme .modeBtn{background:#10070e;border-color:var(--cli-line);color:var(--cli-text)}body.pinkTheme .navBtn.sel,body.pinkTheme .rbtn.ok,body.pinkTheme .chip.on,body.pinkTheme .themeBtn.on{background:var(--cli-accent);color:#210416;border-color:var(--cli-accent)}body.pinkTheme .state{background:#11070f;border-color:var(--cli-line);color:var(--cli-accent)}body.pinkTheme .swipePad{background:radial-gradient(circle at 50% 45%,var(--cli-accent-soft),#050105 62%)}body.pinkTheme .toolBtn.danger,body.pinkTheme .timerChoice.cancel{background:#210711;color:#ff9bcf;border-color:#ff79c644}body.pinkTheme .toast{background:#160914dd;color:var(--cli-accent)}

/* iOS Home Screen / standalone: use every available pixel. */
body.standaloneMode .appShell{grid-template-rows:minmax(0,1fr) var(--nav);padding-top:calc(env(safe-area-inset-top) + 5px)}body.standaloneMode .header{display:none}body.standaloneMode .remoteView{grid-template-rows:25px minmax(0,1fr);padding-top:6px}body.standaloneMode .appsView,body.standaloneMode .toolsView{padding-top:7px}body.standaloneMode .dpadPanel{grid-template-rows:minmax(0,1fr) 42px 42px}body.standaloneMode .swipePad{width:min(100%,520px)}
'''
s = s.replace('</style>', css + '\n</style>', 1)

# State fields: remember local remote mode and standalone state.
old_state = "controlState:'checking'};"
new_state = "controlState:'checking',remoteMode:(localStorage.getItem('remoteMode')||'buttons'),standalone:false};"
if old_state not in s:
    raise SystemExit("v2.9 state marker not found")
s = s.replace(old_state, new_state, 1)

# Insert remote mode helpers before setTab().
marker = "function setTab(t){"
helpers = r'''
function isStandalone(){return window.navigator.standalone===true||window.matchMedia('(display-mode: standalone)').matches}
function applyStandalone(){S.standalone=isStandalone();document.body.classList.toggle('standaloneMode',S.standalone)}
function applyRemoteMode(mode){S.remoteMode=mode==='swipe'?'swipe':'buttons';localStorage.setItem('remoteMode',S.remoteMode);const d=$('dpad'),p=$('swipePad'),b=$('remoteModeBtn');if(!d||!p||!b)return;d.classList.toggle('off',S.remoteMode==='swipe');p.classList.toggle('on',S.remoteMode==='swipe');b.textContent=S.remoteMode==='swipe'?'KEYS':'SWIPE'}
function toggleRemoteMode(){applyRemoteMode(S.remoteMode==='swipe'?'buttons':'swipe');noteUse()}
let swipeStartX=0,swipeStartY=0,swipePointer=null;
function swipeStart(e){if(S.remoteMode!=='swipe')return;swipePointer=e.pointerId;swipeStartX=e.clientX;swipeStartY=e.clientY;$('swipePad').classList.add('active');try{$('swipePad').setPointerCapture(e.pointerId)}catch(_){}e.preventDefault()}
function swipeEnd(e){if(S.remoteMode!=='swipe'||swipePointer!==e.pointerId)return;const dx=e.clientX-swipeStartX,dy=e.clientY-swipeStartY,ax=Math.abs(dx),ay=Math.abs(dy);swipePointer=null;$('swipePad').classList.remove('active');e.preventDefault();if(Math.max(ax,ay)<24){remote('ok');return}if(Math.max(ax,ay)<38)return;if(ax>ay)remote(dx>0?'right':'left');else remote(dy>0?'down':'up')}
'''
if marker not in s:
    raise SystemExit("v2.9 setTab marker not found")
s = s.replace(marker, helpers + marker, 1)

# Add listeners alongside existing remote buttons.
listener_marker = "document.querySelectorAll('[data-key]').forEach(b=>b.onclick=()=>remote(b.dataset.key));"
listener_repl = listener_marker + "$('remoteModeBtn').onclick=toggleRemoteMode;$('swipePad').addEventListener('pointerdown',swipeStart,{passive:false});$('swipePad').addEventListener('pointerup',swipeEnd,{passive:false});$('swipePad').addEventListener('pointercancel',e=>{$('swipePad').classList.remove('active');swipePointer=null});"
if listener_marker not in s:
    raise SystemExit("v2.9 remote listener marker not found")
s = s.replace(listener_marker, listener_repl, 1)

# 90 sec fallback after wake, and initialize standalone + remote mode.
s = s.replace("S.remain=d.remainingMs||30000;", "S.remain=d.remainingMs||90000;")
s = s.replace("saveHidden();sync();setInterval", "applyStandalone();applyRemoteMode(S.remoteMode);saveHidden();sync();setInterval", 1)
s = s.replace("addEventListener('resize',()=>{S.page=0;renderApps()});", "addEventListener('resize',()=>{applyStandalone();S.page=0;renderApps()});")

p.write_text(s, encoding="utf-8")
