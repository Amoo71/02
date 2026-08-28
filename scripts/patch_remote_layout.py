from pathlib import Path

p = Path("app/src/main/assets/index.html")
s = p.read_text(encoding="utf-8")

old = '.remoteView{padding:12px;display:grid;grid-template-rows:auto minmax(0,1fr);gap:9px}.sectionTitle{font-size:12px;color:#8d8d95;font-weight:750;text-transform:uppercase;letter-spacing:.08em;padding:2px 4px}.remoteGrid{min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 92px;gap:10px}.dpadPanel,.sidePanel{border:1px solid var(--line);border-radius:21px;background:#0c0c10;padding:10px;min-height:0}.dpadPanel{display:grid;grid-template-rows:minmax(0,1fr) 58px;gap:9px}.dpad{height:100%;max-height:330px;aspect-ratio:1;margin:auto;display:grid;grid-template:repeat(3,1fr)/repeat(3,1fr);gap:7px}.rbtn{border:1px solid #ffffff12;background:linear-gradient(#29292f,#1b1b20);color:#f7f7f8;border-radius:18px;font-weight:800;font-size:20px;box-shadow:inset 0 1px #ffffff12,0 8px 20px #0005}.rbtn:active{transform:scale(.95);background:#131317}.rbtn.ok{background:#f4f4f5;color:#111}.utilityRow{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.utilityRow .rbtn{font-size:12px;border-radius:14px}.sidePanel{display:grid;grid-template-rows:1fr 1fr 1fr;gap:8px}.sidePanel .rbtn{font-size:13px}.mute{color:#ffb3ae}'

new = '.remoteView{padding:10px;display:grid;grid-template-rows:auto minmax(0,1fr);gap:7px}.sectionTitle{font-size:12px;color:#8d8d95;font-weight:750;text-transform:uppercase;letter-spacing:.08em;padding:2px 4px}.remoteGrid{min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 68px;gap:7px}.dpadPanel,.sidePanel{border:1px solid var(--line);border-radius:19px;background:#0c0c10;min-height:0}.dpadPanel{padding:8px;display:grid;grid-template-rows:minmax(0,1fr) 50px;gap:7px;overflow:hidden}.dpad{width:min(100%,310px);height:auto;aspect-ratio:1;margin:auto;display:grid;grid-template:repeat(3,1fr)/repeat(3,1fr);gap:6px;min-width:0;min-height:0}.rbtn{min-width:0;min-height:0;border:1px solid #ffffff12;background:linear-gradient(#29292f,#1b1b20);color:#f7f7f8;border-radius:16px;font-weight:800;font-size:18px;box-shadow:inset 0 1px #ffffff12,0 8px 20px #0005}.rbtn:active{transform:scale(.95);background:#131317}.rbtn.ok{background:#f4f4f5;color:#111}.utilityRow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.utilityRow .rbtn{font-size:11px;border-radius:13px}.sidePanel{padding:6px;display:grid;grid-template-rows:repeat(3,58px);align-content:center;gap:7px;overflow:hidden}.sidePanel .rbtn{font-size:10px;border-radius:13px;padding:0 2px;line-height:1.05}.mute{color:#ffb3ae}'

if old not in s:
    raise SystemExit("Remote CSS block not found")
s = s.replace(old, new)

s = s.replace(
    '@media(max-width:380px){.appGrid{grid-template-columns:repeat(3,minmax(0,1fr))}.appsBar{grid-template-columns:minmax(0,1fr) auto}.chip.sys{display:none}.remoteGrid{grid-template-columns:minmax(0,1fr) 78px}.rbtn{border-radius:15px}}',
    '@media(max-width:380px){.appGrid{grid-template-columns:repeat(3,minmax(0,1fr))}.appsBar{grid-template-columns:minmax(0,1fr) auto}.chip.sys{display:none}.remoteGrid{grid-template-columns:minmax(0,1fr) 60px;gap:5px}.sidePanel{padding:5px;grid-template-rows:repeat(3,52px);gap:5px}.sidePanel .rbtn{font-size:9px}.dpadPanel{padding:6px}.dpad{gap:5px}.rbtn{border-radius:14px}}'
)

p.write_text(s, encoding="utf-8")
