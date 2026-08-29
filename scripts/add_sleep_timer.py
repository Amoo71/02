from pathlib import Path

# ---- Backend ---------------------------------------------------------------
p = Path("app/src/main/java/dev/fireweb/remote/FireWebService.java")
s = p.read_text(encoding="utf-8")

s = s.replace(
    'import android.content.Intent;\n',
    'import android.content.Intent;\nimport android.content.SharedPreferences;\n'
)

s = s.replace(
    'import java.util.concurrent.Executors;\n',
    'import java.util.concurrent.Executors;\nimport java.util.concurrent.ScheduledExecutorService;\nimport java.util.concurrent.ScheduledFuture;\nimport java.util.concurrent.TimeUnit;\n'
)

s = s.replace(
    '    private static final String UPDATE_URL = "https://raw.githubusercontent.com/Amoo71/02/main/dist/FireWebRemote.apk";\n',
    '    private static final String UPDATE_URL = "https://raw.githubusercontent.com/Amoo71/02/main/dist/FireWebRemote.apk";\n'
    '    private static final String STATE_PREFS = "fireweb_state";\n'
    '    private static final String SLEEP_TIMER_DEADLINE = "sleep_timer_deadline";\n'
)

s = s.replace(
    '    private final ExecutorService pool = Executors.newFixedThreadPool(3);\n',
    '    private final ExecutorService pool = Executors.newFixedThreadPool(3);\n'
    '    private final ScheduledExecutorService sleepScheduler = Executors.newSingleThreadScheduledExecutor();\n'
    '    private volatile ScheduledFuture<?> sleepTimerFuture;\n'
)

s = s.replace(
    '        running = true;\n        new Thread(new Runnable() {',
    '        running = true;\n        restoreSleepTimer();\n        new Thread(new Runnable() {'
)

route_needle = '''        if ("/api/update".equals(path)) {
            markActive();
            return jsonResponse(updateJson());
        }
'''
route_replacement = '''        if ("/api/sleep-timer".equals(path)) {
            markActive();
            String action = param(query, "action");
            if ("set".equals(action)) {
                int hours;
                try { hours = Integer.parseInt(param(query, "hours")); }
                catch (Exception e) { return badRequest("Invalid hours"); }
                if (hours < 1 || hours > 3) return badRequest("Sleep timer must be 1, 2 or 3 hours");
                return jsonResponse(setSleepTimerJson(hours));
            }
            if ("cancel".equals(action)) return jsonResponse(cancelSleepTimerJson());
            if ("status".equals(action) || action.length() == 0) return jsonResponse(sleepTimerStatusJson());
            return badRequest("Unknown sleep timer action");
        }

        if ("/api/update".equals(path)) {
            markActive();
            return jsonResponse(updateJson());
        }
'''
if route_needle not in s:
    raise SystemExit("Update route block not found")
s = s.replace(route_needle, route_replacement)

s = s.replace(
    '''            if ("sleep".equals(type)) {
                String r = adb("input keyevent 223");
                forceIdle();
                return jsonResponse(resultJson("Sleep", r));
            }''',
    '''            if ("sleep".equals(type)) {
                cancelSleepTimer();
                String r = adb("input keyevent 223");
                forceIdle();
                return jsonResponse(resultJson("Sleep", r));
            }'''
)

status_needle = '''                ",\\\"idleTimeoutMs\\\":" + IDLE_TIMEOUT_MS +
                ",\\\"port\\\":" + PORT +'''
status_replacement = '''                ",\\\"idleTimeoutMs\\\":" + IDLE_TIMEOUT_MS +
                ",\\\"sleepTimerRemainingMs\\\":" + sleepTimerRemainingMs() +
                ",\\\"port\\\":" + PORT +'''
if status_needle not in s:
    raise SystemExit("Status JSON block not found")
s = s.replace(status_needle, status_replacement)

methods_needle = '    private String appsJson() {\n'
methods = r'''    private SharedPreferences statePrefs() {
        return getSharedPreferences(STATE_PREFS, MODE_PRIVATE);
    }

    private String setSleepTimerJson(int hours) {
        long deadline = System.currentTimeMillis() + hours * 60L * 60L * 1000L;
        statePrefs().edit().putLong(SLEEP_TIMER_DEADLINE, deadline).apply();
        scheduleSleepTimer(deadline);
        long remaining = sleepTimerRemainingMs();
        return "{\"ok\":true,\"active\":true,\"hours\":" + hours +
                ",\"remainingMs\":" + remaining +
                ",\"message\":\"Sleep timer set for " + hours + " hour" + (hours == 1 ? "" : "s") + ".\"}";
    }

    private String cancelSleepTimerJson() {
        cancelSleepTimer();
        return "{\"ok\":true,\"active\":false,\"remainingMs\":0,\"message\":\"Sleep timer cancelled.\"}";
    }

    private String sleepTimerStatusJson() {
        long remaining = sleepTimerRemainingMs();
        return "{\"ok\":true,\"active\":" + (remaining > 0) +
                ",\"remainingMs\":" + remaining + "}";
    }

    private long sleepTimerRemainingMs() {
        long deadline = statePrefs().getLong(SLEEP_TIMER_DEADLINE, 0L);
        if (deadline <= 0L) return 0L;
        return Math.max(0L, deadline - System.currentTimeMillis());
    }

    private void restoreSleepTimer() {
        long deadline = statePrefs().getLong(SLEEP_TIMER_DEADLINE, 0L);
        if (deadline <= 0L) return;
        if (deadline <= System.currentTimeMillis()) {
            statePrefs().edit().remove(SLEEP_TIMER_DEADLINE).apply();
            return;
        }
        scheduleSleepTimer(deadline);
    }

    private synchronized void scheduleSleepTimer(final long deadline) {
        if (sleepTimerFuture != null) sleepTimerFuture.cancel(false);
        long delay = Math.max(1000L, deadline - System.currentTimeMillis());
        sleepTimerFuture = sleepScheduler.schedule(new Runnable() {
            @Override public void run() { fireSleepTimer(); }
        }, delay, TimeUnit.MILLISECONDS);
    }

    private synchronized void cancelSleepTimer() {
        if (sleepTimerFuture != null) {
            sleepTimerFuture.cancel(false);
            sleepTimerFuture = null;
        }
        statePrefs().edit().remove(SLEEP_TIMER_DEADLINE).apply();
    }

    private void fireSleepTimer() {
        statePrefs().edit().remove(SLEEP_TIMER_DEADLINE).apply();
        synchronized (this) { sleepTimerFuture = null; }
        Log.i(TAG, "Sleep timer fired");
        adb("input keyevent 223");
        forceIdle();
    }

'''
if methods_needle not in s:
    raise SystemExit("appsJson method not found")
s = s.replace(methods_needle, methods + methods_needle, 1)

s = s.replace(
    '    @Override public void onDestroy() { running = false; closeServer(); pool.shutdownNow(); super.onDestroy(); }',
    '    @Override public void onDestroy() { running = false; closeServer(); pool.shutdownNow(); if (sleepTimerFuture != null) sleepTimerFuture.cancel(false); sleepScheduler.shutdownNow(); super.onDestroy(); }'
)

p.write_text(s, encoding="utf-8")

# ---- Web UI ----------------------------------------------------------------
p = Path("app/src/main/assets/index.html")
s = p.read_text(encoding="utf-8")

old_tools_css = '.toolsView{padding:12px;display:grid;grid-template-rows:auto minmax(0,1fr);gap:9px}.toolGrid{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr 1fr;gap:8px;min-height:0}.toolBtn{border:1px solid var(--line);border-radius:19px;background:linear-gradient(150deg,#242429,#151519);color:#fff;text-align:left;padding:14px;font-weight:750;font-size:13px;box-shadow:inset 0 1px #ffffff0d}.toolBtn span{display:block;font-size:10px;font-weight:500;color:#7f7f87;margin-top:5px;line-height:1.25}.toolBtn:active{transform:scale(.98)}.toolBtn.primary{background:#f3f3f5;color:#111}.toolBtn.primary span{color:#555}.toolBtn.danger{grid-column:1/-1;color:#ff8d85;background:#211719}.quickPair{display:grid;grid-template-columns:1fr 1fr;gap:8px;grid-column:1/-1}'
new_tools_css = '.toolsView{padding:10px;display:grid;grid-template-rows:auto minmax(0,1fr);gap:7px}.toolGrid{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto auto auto minmax(54px,.8fr);gap:7px;min-height:0}.toolBtn{min-height:0;border:1px solid var(--line);border-radius:16px;background:linear-gradient(150deg,#242429,#151519);color:#fff;text-align:left;padding:10px 11px;font-weight:750;font-size:12px;box-shadow:inset 0 1px #ffffff0d}.toolBtn span{display:block;font-size:9px;font-weight:500;color:#7f7f87;margin-top:3px;line-height:1.2}.toolBtn:active{transform:scale(.98)}.toolBtn.primary{background:#f3f3f5;color:#111}.toolBtn.primary span{color:#555}.toolBtn.danger{color:#ff8d85;background:#211719}.quickPair{display:grid;grid-template-columns:1fr 1fr;gap:7px;grid-column:1/-1}.timerCard{grid-column:1/-1;border:1px solid var(--line);border-radius:17px;background:#0c0c10;padding:9px 10px;display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:9px;min-height:0}.timerInfo{min-width:76px}.timerTitle{font-size:11px;font-weight:800}.timerState{font-size:9px;color:#8a8a92;margin-top:3px;white-space:nowrap}.timerChoices{display:grid;grid-template-columns:repeat(4,1fr);gap:5px}.timerChoice{height:34px;border:1px solid var(--line);border-radius:11px;background:#242429;color:#eee;font-size:10px;font-weight:800}.timerChoice:active{transform:scale(.96)}.timerChoice.cancel{color:#ff9b94;background:#211719}'
if old_tools_css not in s:
    raise SystemExit("Tools CSS block not found")
s = s.replace(old_tools_css, new_tools_css)

old_tools_html = '<section id="toolsView" class="view"><div class="glass toolsView"><div class="sectionTitle">Tools</div><div class="toolGrid"><div class="quickPair"><button class="toolBtn primary" data-launch="org.smarttube.stable">SmartTube<span>Quick launch</span></button><button class="toolBtn primary" data-launch="net.vypn.app">VYPN<span>Quick launch</span></button></div><button class="toolBtn" data-tool="kill-background">Clean Background<span>Kill cached and background processes</span></button><button class="toolBtn" data-tool="trim-cache">Trim Caches<span>Ask Fire OS to reclaim cache</span></button><button class="toolBtn" data-key="home">Home<span>Return to Fire TV launcher</span></button><button class="toolBtn" data-key="back">Back<span>Send Android Back</span></button><button class="toolBtn danger" data-tool="sleep">Sleep Fire TV<span>Sleep display and enter Ultra Idle immediately</span></button></div></div></section>'
new_tools_html = '<section id="toolsView" class="view"><div class="glass toolsView"><div class="sectionTitle">Tools</div><div class="toolGrid"><div class="quickPair"><button class="toolBtn primary" data-launch="org.smarttube.stable">SmartTube<span>Quick launch</span></button><button class="toolBtn primary" data-launch="net.vypn.app">VYPN<span>Quick launch</span></button></div><button class="toolBtn" data-tool="kill-background">Clean Background<span>Kill cached/background apps</span></button><button class="toolBtn" data-tool="trim-cache">Trim Caches<span>Reclaim app cache</span></button><div class="timerCard"><div class="timerInfo"><div class="timerTitle">Sleep Timer</div><div id="sleepTimerState" class="timerState">Off</div></div><div class="timerChoices"><button class="timerChoice" data-sleep-hours="1">1h</button><button class="timerChoice" data-sleep-hours="2">2h</button><button class="timerChoice" data-sleep-hours="3">3h</button><button id="sleepTimerCancel" class="timerChoice cancel">Off</button></div></div><button id="updateBtn" class="toolBtn">Update<span>Download latest build</span></button><button class="toolBtn danger" data-tool="sleep">Sleep Now<span>Fire TV + TV via HDMI-CEC</span></button></div></div></section>'
if old_tools_html not in s:
    raise SystemExit("Tools HTML block not found")
s = s.replace(old_tools_html, new_tools_html)

s = s.replace(
    "const S={apps:[],idle:true,remain:0,page:0,system:false,showHidden:false,selected:null,hidden:new Set(JSON.parse(localStorage.getItem('hiddenApps')||'[]')),lastUse:Date.now(),lastPing:0};",
    "const S={apps:[],idle:true,remain:0,sleepTimer:0,page:0,system:false,showHidden:false,selected:null,hidden:new Set(JSON.parse(localStorage.getItem('hiddenApps')||'[]')),lastUse:Date.now(),lastPing:0};"
)

function_needle = "async function tool(type){try{const d=await api('/api/tool?type='+encodeURIComponent(type));if(type==='sleep')showIdle();else S.remain=30000;toast(d.message||'Done')}catch(e){toast(e.message)}}\n"
function_replacement = function_needle + "function formatSleep(ms){if(!ms||ms<=0)return 'Off';const total=Math.max(1,Math.ceil(ms/60000));const h=Math.floor(total/60),m=total%60;return h>0?(h+'h '+String(m).padStart(2,'0')+'m'):(m+'m')}\nfunction renderSleepTimer(){$('sleepTimerState').textContent=S.sleepTimer>0?'Turns off in '+formatSleep(S.sleepTimer):'Off'}\nasync function setSleepTimer(hours){try{const d=await api('/api/sleep-timer?action=set&hours='+hours);S.sleepTimer=d.remainingMs||hours*3600000;renderSleepTimer();toast(d.message||('Sleep in '+hours+'h'))}catch(e){toast(e.message)}}\nasync function cancelSleepTimer(){try{const d=await api('/api/sleep-timer?action=cancel');S.sleepTimer=0;renderSleepTimer();toast(d.message||'Sleep timer cancelled')}catch(e){toast(e.message)}}\nasync function updateApp(){if(!confirm('Download and install the latest Fire Web Remote APK?'))return;const b=$('updateBtn');b.disabled=true;try{toast('Downloading update…');const d=await api('/api/update');toast(d.message||'Restarting…');setTimeout(()=>location.reload(),9000)}catch(e){b.disabled=false;toast(e.message||'Update failed')}}\n"
if function_needle not in s:
    raise SystemExit("tool() function not found")
s = s.replace(function_needle, function_replacement)

sync_old = "async function sync(){try{const d=await api('/api/status',true);S.remain=d.remainingMs||0;$('host').textContent=d.ip+':'+d.port;if(d.idle)showIdle();else{showActive();if(!S.apps.length)await loadApps()}}catch(e){$('state').textContent='Offline'}}"
sync_new = "async function sync(){try{const d=await api('/api/status',true);S.remain=d.remainingMs||0;S.sleepTimer=d.sleepTimerRemainingMs||0;renderSleepTimer();$('host').textContent=d.ip+':'+d.port;if(d.idle)showIdle();else{showActive();if(!S.apps.length)await loadApps()}}catch(e){$('state').textContent='Offline'}}"
if sync_old not in s:
    raise SystemExit("sync() function not found")
s = s.replace(sync_old, sync_new)

listeners_needle = "document.querySelectorAll('.navBtn').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));document.querySelectorAll('[data-key]').forEach(b=>b.onclick=()=>remote(b.dataset.key));document.querySelectorAll('[data-tool]').forEach(b=>b.onclick=()=>tool(b.dataset.tool));document.querySelectorAll('[data-launch]').forEach(b=>b.onclick=()=>action('launch',b.dataset.launch));"
listeners_new = listeners_needle + "document.querySelectorAll('[data-sleep-hours]').forEach(b=>b.onclick=()=>setSleepTimer(Number(b.dataset.sleepHours)));$('sleepTimerCancel').onclick=cancelSleepTimer;$('updateBtn').onclick=updateApp;"
if listeners_needle not in s:
    raise SystemExit("Button listener block not found")
s = s.replace(listeners_needle, listeners_new)

interval_old = "setInterval(()=>{if(!S.idle){S.remain=Math.max(0,S.remain-1000);$('state').textContent='Awake · '+Math.ceil(S.remain/1000)+'s';if(S.remain<=0)sync()}},1000);"
interval_new = "setInterval(()=>{if(S.sleepTimer>0){S.sleepTimer=Math.max(0,S.sleepTimer-1000);renderSleepTimer();if(S.sleepTimer===0)setTimeout(sync,1200)}if(!S.idle){S.remain=Math.max(0,S.remain-1000);$('state').textContent='Awake · '+Math.ceil(S.remain/1000)+'s';if(S.remain<=0)sync()}},1000);"
if interval_old not in s:
    raise SystemExit("Main timer interval not found")
s = s.replace(interval_old, interval_new)

p.write_text(s, encoding="utf-8")
