from pathlib import Path

# FireWebService: 90 second controller idle.
p = Path("app/src/main/java/dev/fireweb/remote/FireWebService.java")
s = p.read_text(encoding="utf-8")
s = s.replace(
    'private static final long IDLE_TIMEOUT_MS = 30_000L;',
    'private static final long IDLE_TIMEOUT_MS = 90_000L;'
)
p.write_text(s, encoding="utf-8")

# AdbClient: serialize local ADB sessions and tolerate the normal socket close
# race at the end of short shell commands (keyevents, monkey, etc.).
p = Path("app/src/main/java/dev/fireweb/remote/AdbClient.java")
s = p.read_text(encoding="utf-8")

if 'private static final Object ADB_LOCK' not in s:
    s = s.replace(
        '    private static final byte[] SIGNATURE_PADDING = createSignaturePadding();\n',
        '    private static final byte[] SIGNATURE_PADDING = createSignaturePadding();\n'
        '    private static final Object ADB_LOCK = new Object();\n'
    )

old_shell = '''    public synchronized String shell(String command, int timeoutMs) throws Exception {
        Exception last = null;
        String[] hosts = new String[] { "127.0.0.1", getLanIp() };
        for (String host : hosts) {
            if (host == null || host.length() == 0) continue;
            try {
                return shellOnHost(host, command, timeoutMs);
            } catch (Exception e) {
                last = e;
            }
        }
        if (last != null) throw last;
        throw new IOException("No local ADB address found");
    }
'''
new_shell = '''    public String shell(String command, int timeoutMs) throws Exception {
        // Every HTTP request creates its own AdbClient instance. A per-instance
        // synchronized method therefore did not prevent overlapping ADB handshakes.
        // Serialize all local ADB sessions process-wide.
        synchronized (ADB_LOCK) {
            Exception last = null;
            String[] hosts = new String[] { "127.0.0.1", getLanIp() };
            for (String host : hosts) {
                if (host == null || host.length() == 0) continue;
                try {
                    return shellOnHost(host, command, timeoutMs);
                } catch (Exception e) {
                    last = e;
                }
            }
            if (last != null) throw last;
            throw new IOException("No local ADB address found");
        }
    }
'''
if old_shell in s:
    s = s.replace(old_shell, new_shell)
elif 'synchronized (ADB_LOCK)' not in s:
    raise SystemExit('AdbClient shell() block not found')

s = s.replace(
    '        socket.setSoTimeout(timeoutMs);\n',
    '        socket.setSoTimeout(timeoutMs);\n        socket.setTcpNoDelay(true);\n'
)

old_write_ack = '''                    result.write(p.data);
                    send(out, A_OKAY, localId, remoteId, new byte[0]);
                } else if (p.command == A_CLSE) {
                    if (remoteId == 0) remoteId = p.arg0;
                    send(out, A_CLSE, localId, remoteId, new byte[0]);
                    break;
'''
new_write_ack = '''                    result.write(p.data);
                    try {
                        send(out, A_OKAY, localId, remoteId, new byte[0]);
                    } catch (IOException e) {
                        // adbd can close immediately after the final WRTE. The command
                        // has already completed and its output is already buffered.
                        if (isNormalClose(e)) break;
                        throw e;
                    }
                } else if (p.command == A_CLSE) {
                    if (remoteId == 0) remoteId = p.arg0;
                    try {
                        send(out, A_CLSE, localId, remoteId, new byte[0]);
                    } catch (IOException e) {
                        // Fire OS often tears down the TCP socket before the host can
                        // acknowledge A_CLSE. Treat Broken pipe/reset as normal EOF.
                        if (!isNormalClose(e)) throw e;
                    }
                    break;
'''
if old_write_ack in s:
    s = s.replace(old_write_ack, new_write_ack)
elif 'if (isNormalClose(e)) break;' not in s:
    raise SystemExit('ADB WRTE/CLSE block not found')

helper_needle = '    private static void writeLeInt(DataOutputStream out, int value) throws IOException {\n'
helper = '''    private static boolean isNormalClose(IOException e) {
        String message = e.getMessage();
        if (message == null) return false;
        message = message.toLowerCase();
        return message.contains("broken pipe") ||
                message.contains("connection reset") ||
                message.contains("socket closed") ||
                message.contains("connection abort");
    }

'''
if 'private static boolean isNormalClose' not in s:
    if helper_needle not in s:
        raise SystemExit('writeLeInt() marker not found')
    s = s.replace(helper_needle, helper + helper_needle)

p.write_text(s, encoding="utf-8")

# Web UI: mirror the backend's new 90 second inactivity window.
p = Path("app/src/main/assets/index.html")
s = p.read_text(encoding="utf-8")

# These replacements run after all older UI patches, so they only affect the
# controller inactivity state, not unrelated network timeouts in Java.
s = s.replace('S.remain=30000', 'S.remain=90000')
s = s.replace('S.remain = 30000', 'S.remain = 90000')
s = s.replace('S.remain= 30000', 'S.remain= 90000')
s = s.replace('data.remainingMs||30000', 'data.remainingMs||90000')
s = s.replace('data.remainingMs || 30000', 'data.remainingMs || 90000')
s = s.replace('Date.now()-S.lastUse<30000', 'Date.now()-S.lastUse<90000')
s = s.replace('Date.now() - S.lastUse < 30000', 'Date.now() - S.lastUse < 90000')

p.write_text(s, encoding="utf-8")
