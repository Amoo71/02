from pathlib import Path

# Fire OS can immediately close an ADB transport when the host advertises an
# insufficient max payload in CNXN. v2.6 still inherited the old 4096-byte
# value. Modern ADB hosts advertise 256 KiB while remaining compatible with
# older daemons, which negotiate their own smaller receive size in reply.
p = Path("app/src/main/java/dev/fireweb/remote/AdbClient.java")
s = p.read_text(encoding="utf-8")

old = '    private static final int MAX_DATA = 4096;\n'
new = '    private static final int MAX_DATA = 256 * 1024;\n'

if old not in s:
    if new not in s:
        raise SystemExit("ADB MAX_DATA marker not found")
else:
    s = s.replace(old, new, 1)

# Keep the initial banner conservative: no feature is advertised unless this
# embedded client actually implements it. The identity remains a valid
# host:<serial>:<banner> string.
s = s.replace(
    'send(out, A_CNXN, ADB_VERSION, MAX_DATA, "host::fireweb\\0".getBytes("UTF-8"));',
    'send(out, A_CNXN, ADB_VERSION, MAX_DATA, "host::fireweb\\0".getBytes("UTF-8"));'
)

p.write_text(s, encoding="utf-8")
