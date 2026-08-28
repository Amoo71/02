from pathlib import Path

p = Path("app/src/main/java/dev/fireweb/remote/FireWebService.java")
s = p.read_text(encoding="utf-8")

s = s.replace(
    'if ("trim-cache".equals(type)) return jsonResponse(resultJson("Trim caches", adb("pm trim-caches 999999999999"));',
    'if ("trim-cache".equals(type)) return jsonResponse(resultJson("Trim caches", adb("pm trim-caches 999999999999")));'
)

s = s.replace(
    'String script =\n                    ("sleep 3; " +',
    'String script =\n                    "(sleep 3; " +'
)

needle = '            cachedIndex = new String(out.toByteArray(), "UTF-8");\n            return cachedIndex;'
replacement = '''            cachedIndex = new String(out.toByteArray(), "UTF-8");
            String uiPatch = "<script>(function(){try{" +
                    "var g=document.querySelector('#toolsView .toolGrid');if(!g)return;" +
                    "var h=g.querySelector('[data-key=\\\"home\\\"]');if(h)h.remove();" +
                    "var b=g.querySelector('[data-key=\\\"back\\\"]');if(b)b.remove();" +
                    "var sl=g.querySelector('[data-tool=\\\"sleep\\\"]');if(sl)sl.style.gridColumn='auto';" +
                    "var u=document.createElement('button');u.id='updateBtn';u.className='toolBtn';" +
                    "u.innerHTML='Update<span>Download latest APK and restart</span>';" +
                    "u.onclick=async function(){if(!confirm('Download and install the latest Fire Web Remote APK?'))return;" +
                    "u.disabled=true;try{toast('Downloading update…');var d=await api('/api/update');" +
                    "toast(d.message||'Restarting…');setTimeout(function(){location.reload()},9000)}" +
                    "catch(e){u.disabled=false;toast(e.message||'Update failed')}};" +
                    "if(sl)g.insertBefore(u,sl);else g.appendChild(u);" +
                    "}catch(e){}})();</script>";
            cachedIndex = cachedIndex.replace("</body>", uiPatch + "</body>");
            return cachedIndex;'''

if needle in s:
    s = s.replace(needle, replacement)

p.write_text(s, encoding="utf-8")
