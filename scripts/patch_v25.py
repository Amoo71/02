from pathlib import Path

# ---------------------------------------------------------------------------
# Backend: shared UI state stored centrally on the Fire TV.
# ---------------------------------------------------------------------------
p = Path("app/src/main/java/dev/fireweb/remote/FireWebService.java")
s = p.read_text(encoding="utf-8")

# add preference keys after the sleep timer constants injected by v2.2
needle = '    private static final String SLEEP_TIMER_DEADLINE = "sleep_timer_deadline";\n'
insert = needle + '''    private static final String UI_APP_ORDER = "ui_app_order";
    private static final String UI_HIDDEN_APPS = "ui_hidden_apps";
    private static final String UI_THEME = "ui_theme";
'''
if needle in s and 'UI_APP_ORDER' not in s:
    s = s.replace(needle, insert)

# UI state is intentionally available while controller is idle so the page can
# load the shared theme/preferences without waking the Fire TV.
route_needle = '''        if ("/api/status".equals(path)) return jsonResponse(statusJson());
        if ("/api/wake".equals(path)) return jsonResponse(wakeJson());
'''
route_replacement = '''        if ("/api/status".equals(path)) return jsonResponse(statusJson());
        if ("/api/wake".equals(path)) return jsonResponse(wakeJson());

        if ("/api/ui-state".equals(path)) {
            String action = param(query, "action");
            if (action.length() == 0 || "get".equals(action)) return jsonResponse(uiStateJson());
            if ("order".equals(action)) return jsonResponse(saveUiListJson(UI_APP_ORDER, param(query, "value")));
            if ("hidden".equals(action)) return jsonResponse(saveUiListJson(UI_HIDDEN_APPS, param(query, "value")));
            if ("theme".equals(action)) return jsonResponse(saveThemeJson(param(query, "value")));
            return badRequest("Unknown UI state action");
        }
'''
if route_needle not in s:
    raise SystemExit('status/wake route marker not found')
s = s.replace(route_needle, route_replacement, 1)

methods_needle = '    private String appsJson() {\n'
methods = r'''    private String uiStateJson() {
        String order = statePrefs().getString(UI_APP_ORDER, "");
        String hidden = statePrefs().getString(UI_HIDDEN_APPS, "");
        String theme = statePrefs().getString(UI_THEME, "dark");
        if (!"pink".equals(theme)) theme = "dark";
        return "{\"ok\":true,\"order\":" + csvJsonArray(order) +
                ",\"hidden\":" + csvJsonArray(hidden) +
                ",\"theme\":\"" + json(theme) + "\"}";
    }

    private String saveUiListJson(String key, String value) {
        if (value == null) value = "";
        if (value.length() > 16000) return "{\"ok\":false,\"error\":\"UI state too large\"}";
        String[] parts = value.split(",");
        StringBuilder clean = new StringBuilder();
        int count = 0;
        for (String part : parts) {
            if (part == null || part.length() == 0 || !isSafePackage(part)) continue;
            if (count++ >= 500) break;
            if (clean.length() > 0) clean.append(',');
            clean.append(part);
        }
        statePrefs().edit().putString(key, clean.toString()).apply();
        return "{\"ok\":true}";
    }

    private String saveThemeJson(String value) {
        String theme = "pink".equals(value) ? "pink" : "dark";
        statePrefs().edit().putString(UI_THEME, theme).apply();
        return "{\"ok\":true,\"theme\":\"" + theme + "\"}";
    }

    private String csvJsonArray(String csv) {
        StringBuilder out = new StringBuilder("[");
        if (csv != null && csv.length() > 0) {
            String[] parts = csv.split(",");
            boolean first = true;
            for (String part : parts) {
                if (!isSafePackage(part)) continue;
                if (!first) out.append(',');
                first = false;
                out.append('"').append(json(part)).append('"');
            }
        }
        return out.append(']').toString();
    }

'''
if methods_needle not in s:
    raise SystemExit('appsJson marker not found')
if 'private String uiStateJson()' not in s:
    s = s.replace(methods_needle, methods + methods_needle, 1)

p.write_text(s, encoding="utf-8")

# ---------------------------------------------------------------------------
# Frontend: synchronized app order/hidden state + pink theme.
# Runs after v2.3/v2.4 patches.
# ---------------------------------------------------------------------------
p = Path("app/src/main/assets/index.html")
s = p.read_text(encoding="utf-8")

# Apps bar gets Arrange control.
s = s.replace(
    '.appsBar{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:7px}',
    '.appsBar{display:grid;grid-template-columns:minmax(0,1fr) auto auto auto;gap:7px}'
)
s = s.replace(
    '@media(max-width:380px){.appGrid{grid-template-columns:repeat(3,minmax(0,1fr))}.appsBar{grid-template-columns:minmax(0,1fr) auto}',
    '@media(max-width:380px){.appGrid{grid-template-columns:repeat(3,minmax(0,1fr))}.appsBar{grid-template-columns:minmax(0,1fr) auto auto}'
)

# UI state/arrange/theme CSS appended before </style>.
extra_css = r'''
/* synced arrange mode */
.tile.arrangeMode{outline:1px dashed #ffffff38;cursor:move}.tile.arrangeMode .more{display:none}.tile.arrangePicked{outline:2px solid #fff;transform:scale(.96);box-shadow:0 0 0 4px #ffffff18,inset 0 1px #ffffff18}.chip.arrange.on{background:#f4f4f5;color:#111}.themeCard{grid-column:1/-1;height:44px;border:1px solid var(--line);border-radius:15px;background:#0c0c10;padding:5px 6px;display:grid;grid-template-columns:auto 1fr 1fr;gap:5px;align-items:center}.themeLabel{font-size:10px;font-weight:800;padding:0 5px;color:#9a9aa2}.themeBtn{height:32px;border:1px solid var(--line);border-radius:10px;background:#242429;color:#aaa;font-size:10px;font-weight:800}.themeBtn.on{background:#f4f4f5;color:#111}
/* Pink / girly theme */
body.pinkTheme{--panel:#2b1728e8;--panel2:#1d0d1b;--line:#ffb6df25;--text:#fff5fb;--muted:#d69abd;--danger:#ff7faf;background:radial-gradient(circle at 50% -12%,#ff83c6 0,#71375e 25%,#261020 55%,#090508 88%)}body.pinkTheme .orb{background:linear-gradient(145deg,#ffd5eb,#ff78bd);box-shadow:inset 0 1px 1px #fff8,0 10px 28px #ff4aaa30}body.pinkTheme .glass,body.pinkTheme .nav{border-color:#ffb8dd26;background:#241320e8}body.pinkTheme .navBtn.sel,body.pinkTheme .rbtn.ok,body.pinkTheme .chip.on,body.pinkTheme .themeBtn.on{background:linear-gradient(145deg,#fff2fa,#ffc4e5);color:#5e183f}body.pinkTheme .tile{background:linear-gradient(150deg,#48203e,#1d0d1a 72%);border-color:#ffc3e41c}body.pinkTheme .iconBox{background:#5a294c;box-shadow:0 9px 25px #0008,inset 0 1px #ffd8ec25}body.pinkTheme .rbtn,body.pinkTheme .toolBtn,body.pinkTheme .timerChoice{background:linear-gradient(#4a2440,#291222);border-color:#ffc0e31d}body.pinkTheme .timerCard,body.pinkTheme .themeCard,body.pinkTheme .dpadPanel{background:#1b0c18;border-color:#ffb8dc22}body.pinkTheme .state{background:#3a1d33;border-color:#ffbadf24;color:#ffd8ed}body.pinkTheme .search{background:#160a14;border-color:#ffb8dc20}body.pinkTheme .toolBtn.danger,body.pinkTheme .timerChoice.cancel{background:#47182d;color:#ff9bc8}body.pinkTheme .mute{color:#ff9ccb}body.pinkTheme .idle{background:radial-gradient(circle at 50% 20%,#8d3f70,#35142d 45%,#080407)}body.pinkTheme .idleCard{background:#2a1425e8;border-color:#ffc0e328}
'''
s = s.replace('</style>', extra_css + '</style>', 1)

# Arrange button after System.
old_apps = '<button id="systemChip" class="chip sys">System</button></div><div id="appGrid"'
new_apps = '<button id="systemChip" class="chip sys">System</button><button id="arrangeChip" class="chip arrange">Arrange</button></div><div id="appGrid"'
if old_apps not in s:
    raise SystemExit('apps bar HTML marker not found')
s = s.replace(old_apps, new_apps, 1)

# Theme card between timer and maintenance buttons.
old_tools = '<button class="toolBtn maintenanceBtn" data-tool="kill-background">Clean Background<span>Kill cached/background apps</span></button>'
new_tools = '<div class="themeCard"><span class="themeLabel">Theme</span><button class="themeBtn" data-theme="dark">Dark</button><button class="themeBtn" data-theme="pink">Pink</button></div>' + old_tools
if old_tools not in s:
    raise SystemExit('tools maintenance marker not found')
s = s.replace(old_tools, new_tools, 1)

# Tool grid gets one extra compact row while remaining one-screen.
s = s.replace(
    '.toolGrid{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto minmax(0,1fr) 46px;gap:7px;min-height:0}',
    '.toolGrid{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto 44px minmax(0,1fr) 44px;gap:7px;min-height:0}'
)

old_state = "const S={apps:[],idle:true,remain:0,sleepTimer:0,page:0,system:false,showHidden:false,selected:null,hidden:new Set(JSON.parse(localStorage.getItem('hiddenApps')||'[]')),lastUse:Date.now(),lastPing:0,debugTapCount:0,debugTapAt:0};"
new_state = "const S={apps:[],idle:true,remain:0,sleepTimer:0,page:0,system:false,showHidden:false,arrange:false,selected:null,selectedArrange:null,hidden:new Set(),order:[],theme:'dark',uiLoaded:false,lastUse:Date.now(),lastPing:0,debugTapCount:0,debugTapAt:0};"
if old_state not in s:
    raise SystemExit('state object not found')
s = s.replace(old_state, new_state, 1)

# No browser-local hidden state: display count only. Persistence is server-side.
old_save = "function saveHidden(){localStorage.setItem('hiddenApps',JSON.stringify([...S.hidden]));$('hiddenChip').textContent='Hidden '+S.hidden.size}"
new_save = "function saveHidden(){$('hiddenChip').textContent='Hidden '+S.hidden.size}\nasync function persistHidden(){try{await api('/api/ui-state?action=hidden&value='+encodeURIComponent([...S.hidden].join(',')))}catch(e){toast('Sync failed')}}\nasync function persistOrder(){try{await api('/api/ui-state?action=order&value='+encodeURIComponent(S.order.join(',')))}catch(e){toast('Sync failed')}}\nfunction applyTheme(t){S.theme=t==='pink'?'pink':'dark';document.body.classList.toggle('pinkTheme',S.theme==='pink');document.querySelectorAll('[data-theme]').forEach(b=>b.classList.toggle('on',b.dataset.theme===S.theme))}\nasync function setTheme(t){applyTheme(t);try{await api('/api/ui-state?action=theme&value='+encodeURIComponent(S.theme));toast(S.theme==='pink'?'Pink theme ✦':'Dark theme')}catch(e){toast('Theme sync failed')}}\nfunction ensureOrder(){const known=new Set(S.order);const missing=S.apps.filter(a=>!known.has(a.package)).sort((a,b)=>a.name.localeCompare(b.name));if(!S.order.length){const pin={'org.smarttube.stable':0,'net.vypn.app':1};missing.sort((a,b)=>(pin[a.package]??99)-(pin[b.package]??99)||a.name.localeCompare(b.name))}missing.forEach(a=>S.order.push(a.package));S.order=S.order.filter(p=>S.apps.some(a=>a.package===p))}\nasync function loadUiState(render=true){try{const d=await api('/api/ui-state');S.order=Array.isArray(d.order)?d.order:[];S.hidden=new Set(Array.isArray(d.hidden)?d.hidden:[]);applyTheme(d.theme||'dark');S.uiLoaded=true;if(S.apps.length){ensureOrder();if(render)renderApps()}else saveHidden()}catch(e){}}"
if old_save not in s:
    raise SystemExit('saveHidden function not found')
s = s.replace(old_save, new_save, 1)

# Custom persistent order replaces alphabetical/pinned sort.
old_filtered = "function filteredApps(){const q=$('search').value.trim().toLowerCase();let a=S.apps.filter(x=>(S.system||!x.system)&&(S.showHidden?S.hidden.has(x.package):!S.hidden.has(x.package))&&(x.name.toLowerCase().includes(q)||x.package.toLowerCase().includes(q)));const pin={'org.smarttube.stable':0,'net.vypn.app':1};a.sort((x,y)=>(pin[x.package]??99)-(pin[y.package]??99)||x.name.localeCompare(y.name));return a}"
new_filtered = "function filteredApps(){const q=$('search').value.trim().toLowerCase();ensureOrder();const pos=new Map(S.order.map((p,i)=>[p,i]));let a=S.apps.filter(x=>(S.system||!x.system)&&(S.showHidden?S.hidden.has(x.package):!S.hidden.has(x.package))&&(x.name.toLowerCase().includes(q)||x.package.toLowerCase().includes(q)));a.sort((x,y)=>(pos.get(x.package)??9999)-(pos.get(y.package)??9999)||x.name.localeCompare(y.name));return a}"
if old_filtered not in s:
    raise SystemExit('filteredApps not found')
s = s.replace(old_filtered, new_filtered, 1)

# Add arrange classes to app tile render.
s = s.replace(
    'class="tile ${S.showHidden?\'hiddenTile\':\'\'}" data-open="${esc(x.package)}"',
    'class="tile ${S.showHidden?\'hiddenTile\':\'\'} ${S.arrange?\'arrangeMode\':\'\'} ${S.selectedArrange===x.package?\'arrangePicked\':\'\'}" data-open="${esc(x.package)}"'
)

# loadApps must merge server order before first render.
old_load = "async function loadApps(){try{const d=await api('/api/apps');S.apps=d.apps||[];renderApps()}catch(e){toast(e.message)}}"
new_load = "async function loadApps(){try{const d=await api('/api/apps');S.apps=d.apps||[];ensureOrder();renderApps()}catch(e){toast(e.message)}}"
if old_load not in s:
    raise SystemExit('loadApps not found')
s = s.replace(old_load, new_load, 1)

# sync loads shared prefs first, even while idle.
old_sync = "async function sync(){try{const d=await api('/api/status',true);S.remain=d.remainingMs||0;S.sleepTimer=d.sleepTimerRemainingMs||0;renderSleepTimer();$('host').textContent=d.ip+':'+d.port;if(d.idle)showIdle();else{showActive();if(!S.apps.length)await loadApps()}}catch(e){$('state').textContent='Offline'}}"
new_sync = "async function sync(){try{if(!S.uiLoaded)await loadUiState(false);const d=await api('/api/status',true);S.remain=d.remainingMs||0;S.sleepTimer=d.sleepTimerRemainingMs||0;renderSleepTimer();$('host').textContent=d.ip+':'+d.port;if(d.idle)showIdle();else{showActive();if(!S.apps.length)await loadApps()}}catch(e){$('state').textContent='Offline'}}"
if old_sync not in s:
    raise SystemExit('sync not found')
s = s.replace(old_sync, new_sync, 1)

# Arrange and theme controls.
listener_marker = "$('systemChip').onclick=()=>{S.system=!S.system;S.page=0;$('systemChip').classList.toggle('on',S.system);renderApps()};$('prevPage').onclick"
listener_replacement = "$('systemChip').onclick=()=>{S.system=!S.system;S.page=0;$('systemChip').classList.toggle('on',S.system);renderApps()};$('arrangeChip').onclick=()=>{S.arrange=!S.arrange;S.selectedArrange=null;$('arrangeChip').classList.toggle('on',S.arrange);toast(S.arrange?'Tap two apps to swap':'Arrangement saved');renderApps()};document.querySelectorAll('[data-theme]').forEach(b=>b.onclick=()=>setTheme(b.dataset.theme));$('prevPage').onclick"
if listener_marker not in s:
    raise SystemExit('system listener marker not found')
s = s.replace(listener_marker, listener_replacement, 1)

# Touch-friendly rearranging: select first app, then tap destination to swap.
old_grid_click = "$('appGrid').onclick=e=>{const more=e.target.closest('[data-more]');if(more){e.stopPropagation();openSheet(more.dataset.more);return}const tile=e.target.closest('[data-open]');if(tile){const a=findApp(tile.dataset.open);if(S.showHidden)openSheet(tile.dataset.open);else if(a&&a.launchable)action('launch',tile.dataset.open);else openSheet(tile.dataset.open)}};"
new_grid_click = "$('appGrid').onclick=e=>{const more=e.target.closest('[data-more]');if(more&&!S.arrange){e.stopPropagation();openSheet(more.dataset.more);return}const tile=e.target.closest('[data-open]');if(!tile)return;const pkg=tile.dataset.open;if(S.arrange){if(!S.selectedArrange){S.selectedArrange=pkg;renderApps();return}if(S.selectedArrange===pkg){S.selectedArrange=null;renderApps();return}ensureOrder();const a=S.order.indexOf(S.selectedArrange),b=S.order.indexOf(pkg);if(a>=0&&b>=0){const tmp=S.order[a];S.order[a]=S.order[b];S.order[b]=tmp;persistOrder()}S.selectedArrange=null;renderApps();return}const app=findApp(pkg);if(S.showHidden)openSheet(pkg);else if(app&&app.launchable)action('launch',pkg);else openSheet(pkg)};"
if old_grid_click not in s:
    raise SystemExit('appGrid onclick not found')
s = s.replace(old_grid_click, new_grid_click, 1)

# Hidden state syncs immediately to server.
old_hide = "$('sheetHide').onclick=()=>{if(!S.selected)return;const p=S.selected.package;if(S.hidden.has(p))S.hidden.delete(p);else S.hidden.add(p);saveHidden();closeSheet();renderApps()};$('wakeBtn').onclick=wake;"
new_hide = "$('sheetHide').onclick=()=>{if(!S.selected)return;const p=S.selected.package;if(S.hidden.has(p))S.hidden.delete(p);else S.hidden.add(p);saveHidden();persistHidden();closeSheet();renderApps()};$('wakeBtn').onclick=wake;"
if old_hide not in s:
    raise SystemExit('sheetHide handler not found')
s = s.replace(old_hide, new_hide, 1)

# Periodic shared-state sync does NOT keep the controller awake because the
# backend ui-state endpoint lives before the idle guard and does not markActive.
s = s.replace(
    'saveHidden();sync();',
    "saveHidden();sync();setInterval(()=>{if(!document.hidden&&!S.arrange)loadUiState(true)},10000);"
)

p.write_text(s, encoding="utf-8")
