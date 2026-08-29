from pathlib import Path

# This patch runs after the v2.2 sleep-timer and compact-remote build patches.

# ---------------- Backend: hidden 1-minute timer action ----------------
p = Path("app/src/main/java/dev/fireweb/remote/FireWebService.java")
s = p.read_text(encoding="utf-8")

needle = '''            if ("cancel".equals(action)) return jsonResponse(cancelSleepTimerJson());
            if ("status".equals(action) || action.length() == 0) return jsonResponse(sleepTimerStatusJson());'''
replacement = '''            if ("debug".equals(action)) {
                long deadline = System.currentTimeMillis() + 60_000L;
                statePrefs().edit().putLong(SLEEP_TIMER_DEADLINE, deadline).apply();
                scheduleSleepTimer(deadline);
                return jsonResponse("{\\\"ok\\\":true,\\\"active\\\":true,\\\"remainingMs\\\":" +
                        sleepTimerRemainingMs() + ",\\\"message\\\":\\\"Sleep timer set.\\\"}");
            }
            if ("cancel".equals(action)) return jsonResponse(cancelSleepTimerJson());
            if ("status".equals(action) || action.length() == 0) return jsonResponse(sleepTimerStatusJson());'''
if needle not in s:
    raise SystemExit("sleep timer route marker not found")
s = s.replace(needle, replacement, 1)
p.write_text(s, encoding="utf-8")

# ---------------- Frontend ----------------
p = Path("app/src/main/assets/index.html")
s = p.read_text(encoding="utf-8")

# Remote CSS: full-width D-pad, two compact control rows below it.
start = s.index('.remoteView{')
end = s.index('\n.toolsView{', start)
remote_css = '''.remoteView{padding:10px;display:grid;grid-template-rows:auto minmax(0,1fr);gap:7px}.sectionTitle{font-size:12px;color:#8d8d95;font-weight:750;text-transform:uppercase;letter-spacing:.08em;padding:2px 4px}.remoteGrid{min-height:0;display:block}.dpadPanel{height:100%;border:1px solid var(--line);border-radius:19px;background:#0c0c10;padding:8px;display:grid;grid-template-rows:minmax(0,1fr) 44px 44px;gap:6px;overflow:hidden}.dpad{width:min(100%,340px);height:auto;max-height:100%;aspect-ratio:1;margin:auto;display:grid;grid-template:repeat(3,1fr)/repeat(3,1fr);gap:6px;min-width:0;min-height:0}.rbtn{min-width:0;min-height:0;border:1px solid #ffffff12;background:linear-gradient(#29292f,#1b1b20);color:#f7f7f8;border-radius:16px;font-weight:800;font-size:18px;box-shadow:inset 0 1px #ffffff12,0 8px 20px #0005}.rbtn:active{transform:scale(.95);background:#131317}.rbtn.ok{background:#f4f4f5;color:#111}.utilityRow,.volumeRow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.utilityRow .rbtn,.volumeRow .rbtn{font-size:11px;border-radius:13px}.volumeRow .rbtn{font-size:10px}.mute{color:#ffb3ae}'''
s = s[:start] + remote_css + s[end:]

# Tools CSS: timer first, maintenance middle, very compact Update/OFF row.
start = s.index('.toolsView{')
end = s.index('\n.idle{', start)
tools_css = '''.toolsView{padding:10px;display:grid;grid-template-rows:auto minmax(0,1fr);gap:7px}.toolGrid{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto minmax(0,1fr) 46px;gap:7px;min-height:0}.toolBtn{min-height:0;border:1px solid var(--line);border-radius:16px;background:linear-gradient(150deg,#242429,#151519);color:#fff;text-align:left;padding:10px 11px;font-weight:750;font-size:12px;box-shadow:inset 0 1px #ffffff0d}.toolBtn span{display:block;font-size:9px;font-weight:500;color:#7f7f87;margin-top:3px;line-height:1.2}.toolBtn:active{transform:scale(.98)}.toolBtn.danger{color:#ff8d85;background:#211719}.toolBtn.compact{height:46px;padding:0 12px;display:flex;align-items:center;justify-content:center;text-align:center;font-size:11px}.timerCard{grid-column:1/-1;border:1px solid var(--line);border-radius:17px;background:#0c0c10;padding:10px;display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:9px;min-height:58px}.timerInfo{min-width:76px}.timerTitle{font-size:11px;font-weight:800}.timerState{font-size:9px;color:#8a8a92;margin-top:3px;white-space:nowrap}.timerChoices{display:grid;grid-template-columns:repeat(4,1fr);gap:5px}.timerChoice{height:34px;border:1px solid var(--line);border-radius:11px;background:#242429;color:#eee;font-size:10px;font-weight:800}.timerChoice:active{transform:scale(.96)}.timerChoice.cancel{color:#ff9b94;background:#211719}.maintenanceBtn{height:100%}'''
s = s[:start] + tools_css + s[end:]

# Replace remote section completely.
remote_start = s.index('<section id="remoteView"')
remote_end = s.index('<section id="toolsView"', remote_start)
remote_html = '''<section id="remoteView" class="view"><div class="glass remoteView"><div class="sectionTitle">Remote</div><div class="remoteGrid"><div class="dpadPanel"><div class="dpad"><span></span><button class="rbtn" data-key="up">▲</button><span></span><button class="rbtn" data-key="left">◀</button><button class="rbtn ok" data-key="ok">OK</button><button class="rbtn" data-key="right">▶</button><span></span><button class="rbtn" data-key="down">▼</button><span></span></div><div class="utilityRow"><button class="rbtn" data-key="back">Back</button><button class="rbtn" data-key="home">Home</button><button class="rbtn" data-key="menu">Menu</button></div><div class="volumeRow"><button class="rbtn" data-key="voldown">VOL −</button><button class="rbtn mute" data-key="mute">MUTE</button><button class="rbtn" data-key="volup">VOL +</button></div></div></div></div></section>
'''
s = s[:remote_start] + remote_html + s[remote_end:]

# Replace tools section: no app quick-launches, sleep timer first, compact Update/OFF.
tools_start = s.index('<section id="toolsView"')
tools_end = s.index('</main>', tools_start)
tools_html = '''<section id="toolsView" class="view"><div class="glass toolsView"><div class="sectionTitle">Tools</div><div class="toolGrid"><div class="timerCard"><div class="timerInfo"><div class="timerTitle">Sleep Timer</div><div id="sleepTimerState" class="timerState">Off</div></div><div class="timerChoices"><button class="timerChoice" data-sleep-hours="1">1h</button><button class="timerChoice" data-sleep-hours="2">2h</button><button class="timerChoice" data-sleep-hours="3">3h</button><button id="sleepTimerCancel" class="timerChoice cancel">OFF</button></div></div><button class="toolBtn maintenanceBtn" data-tool="kill-background">Clean Background<span>Kill cached/background apps</span></button><button class="toolBtn maintenanceBtn" data-tool="trim-cache">Trim Caches<span>Reclaim app cache</span></button><button id="updateBtn" class="toolBtn compact">Update</button><button class="toolBtn danger compact" data-tool="sleep">OFF</button></div></div></section>
'''
s = s[:tools_start] + tools_html + s[tools_end:]

# Replace small-phone media query left over from v2.2 so it no longer references sidePanel.
import re
s = re.sub(
    r'@media\(max-width:380px\)\{[^}]*\.appGrid.*?\}\n',
    '@media(max-width:380px){.appGrid{grid-template-columns:repeat(3,minmax(0,1fr))}.appsBar{grid-template-columns:minmax(0,1fr) auto}.chip.sys{display:none}.dpadPanel{padding:6px;grid-template-rows:minmax(0,1fr) 40px 40px}.dpad{gap:5px}.rbtn{border-radius:14px}.utilityRow,.volumeRow{gap:4px}.timerInfo{min-width:65px}.timerChoices{gap:3px}}\n',
    s,
    count=1,
    flags=re.S,
)

# Add hidden debug tap state.
s = s.replace(
    'lastUse:Date.now(),lastPing:0};',
    'lastUse:Date.now(),lastPing:0,debugTapCount:0,debugTapAt:0};',
    1,
)

# If the source is formatted differently, inject before the closing state object via a fallback.
if 'debugTapCount' not in s:
    s = s.replace('lastPing:0\n};', 'lastPing:0,\n  debugTapCount:0,\n  debugTapAt:0\n};', 1)

old = "async function setSleepTimer(hours){try{const d=await api('/api/sleep-timer?action=set&hours='+hours);S.sleepTimer=d.remainingMs||hours*3600000;renderSleepTimer();toast(d.message||('Sleep in '+hours+'h'))}catch(e){toast(e.message)}}"
new = "async function setSleepTimer(hours){try{if(hours===1){const now=Date.now();S.debugTapCount=(now-S.debugTapAt<2500)?S.debugTapCount+1:1;S.debugTapAt=now;if(S.debugTapCount>=5){S.debugTapCount=0;const d=await api('/api/sleep-timer?action=debug');S.sleepTimer=d.remainingMs||60000;renderSleepTimer();toast(d.message||'Sleep timer set');return}}else{S.debugTapCount=0}const d=await api('/api/sleep-timer?action=set&hours='+hours);S.sleepTimer=d.remainingMs||hours*3600000;renderSleepTimer();toast(d.message||('Sleep in '+hours+'h'))}catch(e){toast(e.message)}}"
if old in s:
    s = s.replace(old, new, 1)
else:
    # Formatted build-source fallback: replace function through the next function declaration.
    m = re.search(r'async function setSleepTimer\(hours\)\{.*?\n\}\n\n\nasync function cancelSleepTimer', s, re.S)
    if not m:
        raise SystemExit("setSleepTimer function not found")
    pretty = '''async function setSleepTimer(hours){
  try{
    if(hours===1){
      const now=Date.now();
      S.debugTapCount=(now-S.debugTapAt<2500)?S.debugTapCount+1:1;
      S.debugTapAt=now;
      if(S.debugTapCount>=5){
        S.debugTapCount=0;
        const data=await api("/api/sleep-timer?action=debug");
        S.sleepTimer=data.remainingMs||60000;
        renderSleepTimer();
        toast(data.message||"Sleep timer set");
        return;
      }
    }else{
      S.debugTapCount=0;
    }
    const data=await api("/api/sleep-timer?action=set&hours="+hours);
    S.sleepTimer=data.remainingMs||hours*3600000;
    renderSleepTimer();
    toast(data.message||("Sleep in "+hours+"h"));
  }catch(e){toast(e.message);}
}


async function cancelSleepTimer'''
    s = s[:m.start()] + pretty + s[m.end():]

p.write_text(s, encoding="utf-8")
