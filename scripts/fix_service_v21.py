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

p.write_text(s, encoding="utf-8")
