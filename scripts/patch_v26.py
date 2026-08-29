from pathlib import Path

# ---------------------------------------------------------------------------
# v2.6: replace the small ADB client with a stage-aware implementation and add
# a self-healing manager. The manager keeps the RSA identity stable, repairs
# stale/broken transports, retries only commands that definitely did not run,
# and performs one controlled key reset if the current key can no longer auth.
# ---------------------------------------------------------------------------

adb_client = r'''package dev.fireweb.remote;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Base64;

import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.math.BigInteger;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.NetworkInterface;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.Collections;
import java.util.Enumeration;

import javax.crypto.Cipher;

public class AdbClient {
    private static final int A_CNXN = 0x4e584e43;
    private static final int A_OPEN = 0x4e45504f;
    private static final int A_OKAY = 0x59414b4f;
    private static final int A_CLSE = 0x45534c43;
    private static final int A_WRTE = 0x45545257;
    private static final int A_AUTH = 0x48545541;

    private static final int ADB_VERSION = 0x01000000;
    private static final int MAX_DATA = 4096;

    private static final int AUTH_TOKEN = 1;
    private static final int AUTH_SIGNATURE = 2;
    private static final int AUTH_RSAPUBLICKEY = 3;

    private static final byte[] SHA1_DIGEST_INFO_PREFIX = new byte[] {
            0x30, 0x21, 0x30, 0x09, 0x06, 0x05, 0x2b, 0x0e,
            0x03, 0x02, 0x1a, 0x05, 0x00, 0x04, 0x14
    };
    private static final byte[] SIGNATURE_PADDING = createSignaturePadding();
    private static final Object ADB_LOCK = new Object();

    private final Context context;
    private final KeyPair keyPair;

    public static class AdbFailure extends IOException {
        public final String stage;
        public final boolean commandMayHaveRun;

        AdbFailure(String stage, boolean commandMayHaveRun, Throwable cause) {
            super("ADB " + stage + ": " + cleanMessage(cause), cause);
            this.stage = stage;
            this.commandMayHaveRun = commandMayHaveRun;
        }

        AdbFailure(String stage, boolean commandMayHaveRun, String message) {
            super("ADB " + stage + ": " + message);
            this.stage = stage;
            this.commandMayHaveRun = commandMayHaveRun;
        }
    }

    public AdbClient(Context context) throws Exception {
        this.context = context.getApplicationContext();
        this.keyPair = loadOrCreateKeyPair();
    }

    public String shell(String command, int timeoutMs) throws Exception {
        synchronized (ADB_LOCK) {
            Exception last = null;
            String lan = getLanIp();
            String[] hosts = new String[] { lan, "127.0.0.1" };

            // New TCP transport for every attempt. This deliberately avoids reusing
            // a half-closed adbd connection after Fire OS has reset it.
            for (int round = 0; round < 3; round++) {
                for (String host : hosts) {
                    if (host == null || host.length() == 0) continue;
                    try {
                        return shellOnHost(host, command, timeoutMs);
                    } catch (AdbFailure e) {
                        last = e;
                        // Never repeat a command after adbd has accepted the shell
                        // stream: a keyevent may already have been injected.
                        if (e.commandMayHaveRun) throw e;
                    } catch (Exception e) {
                        last = e;
                    }
                    try { Thread.sleep(120L + round * 180L); }
                    catch (InterruptedException ignored) {}
                }
            }

            if (last != null) throw last;
            throw new AdbFailure("connect", false, "No local ADB address found");
        }
    }

    private String shellOnHost(String host, String command, int timeoutMs) throws Exception {
        Socket socket = new Socket();
        boolean channelAccepted = false;
        DataInputStream in = null;
        DataOutputStream out = null;

        try {
            try {
                socket.connect(new InetSocketAddress(host, 5555), Math.min(timeoutMs, 4500));
                socket.setSoTimeout(timeoutMs);
                socket.setTcpNoDelay(true);
                socket.setKeepAlive(true);
                in = new DataInputStream(socket.getInputStream());
                out = new DataOutputStream(socket.getOutputStream());
            } catch (Exception e) {
                throw new AdbFailure("connect@" + host, false, e);
            }

            try {
                connect(in, out);
            } catch (AdbFailure e) {
                throw e;
            } catch (Exception e) {
                throw new AdbFailure("handshake@" + host, false, e);
            }

            final int localId = 1;
            try {
                send(out, A_OPEN, localId, 0, ("shell:" + command + "\0").getBytes("UTF-8"));
            } catch (Exception e) {
                throw new AdbFailure("open@" + host, false, e);
            }

            int remoteId = 0;
            ByteArrayOutputStream result = new ByteArrayOutputStream();

            while (true) {
                Packet p;
                try {
                    p = read(in);
                } catch (EOFException e) {
                    if (channelAccepted) break;
                    throw new AdbFailure("shell-read@" + host, false, e);
                } catch (Exception e) {
                    throw new AdbFailure("shell-read@" + host, channelAccepted, e);
                }

                if (p.command == A_OKAY) {
                    channelAccepted = true;
                    remoteId = p.arg0;
                } else if (p.command == A_WRTE) {
                    channelAccepted = true;
                    if (remoteId == 0) remoteId = p.arg0;
                    result.write(p.data);
                    try {
                        send(out, A_OKAY, localId, remoteId, new byte[0]);
                    } catch (IOException e) {
                        // Final WRTE can race the peer's TCP close. We already own
                        // the complete payload, so this is a successful command.
                        if (isNormalClose(e)) break;
                        throw new AdbFailure("write-ack@" + host, true, e);
                    }
                } else if (p.command == A_CLSE) {
                    channelAccepted = true;
                    if (remoteId == 0) remoteId = p.arg0;
                    try {
                        send(out, A_CLSE, localId, remoteId, new byte[0]);
                    } catch (IOException e) {
                        if (!isNormalClose(e)) {
                            throw new AdbFailure("close-ack@" + host, true, e);
                        }
                    }
                    break;
                } else if (p.command == A_AUTH) {
                    throw new AdbFailure("authorization", false,
                            "authorization restarted while opening shell");
                }
            }

            return new String(result.toByteArray(), "UTF-8").trim();
        } finally {
            try { socket.close(); } catch (Exception ignored) {}
        }
    }

    private void connect(DataInputStream in, DataOutputStream out) throws Exception {
        try {
            send(out, A_CNXN, ADB_VERSION, MAX_DATA, "host::fireweb\0".getBytes("UTF-8"));
        } catch (Exception e) {
            throw new AdbFailure("cnxn-send", false, e);
        }

        boolean signatureSent = false;
        boolean publicKeySent = false;
        int authTokensAfterPublicKey = 0;

        while (true) {
            Packet p;
            try {
                p = read(in);
            } catch (SocketTimeoutException e) {
                if (publicKeySent) {
                    throw new AdbFailure("authorization", false,
                            "approval required on Fire TV");
                }
                throw new AdbFailure("cnxn-read", false, e);
            } catch (Exception e) {
                if (publicKeySent && isNormalClose(e)) {
                    throw new AdbFailure("authorization", false,
                            "approval required on Fire TV");
                }
                throw new AdbFailure("cnxn-read", false, e);
            }

            if (p.command == A_CNXN) return;
            if (p.command != A_AUTH || p.arg0 != AUTH_TOKEN) continue;

            if (!signatureSent) {
                try {
                    byte[] signature = signAdbToken(p.data, (RSAPrivateKey) keyPair.getPrivate());
                    send(out, A_AUTH, AUTH_SIGNATURE, 0, signature);
                    signatureSent = true;
                } catch (Exception e) {
                    throw new AdbFailure("auth-signature", false, e);
                }
            } else if (!publicKeySent) {
                try {
                    byte[] publicKey = adbPublicKey((RSAPublicKey) keyPair.getPublic());
                    send(out, A_AUTH, AUTH_RSAPUBLICKEY, 0, publicKey);
                    publicKeySent = true;
                } catch (Exception e) {
                    throw new AdbFailure("auth-public-key", false, e);
                }
            } else {
                authTokensAfterPublicKey++;
                if (authTokensAfterPublicKey >= 2) {
                    throw new AdbFailure("authorization", false,
                            "approval required on Fire TV");
                }
                try {
                    byte[] signature = signAdbToken(p.data, (RSAPrivateKey) keyPair.getPrivate());
                    send(out, A_AUTH, AUTH_SIGNATURE, 0, signature);
                } catch (Exception e) {
                    throw new AdbFailure("auth-retry", false, e);
                }
            }
        }
    }

    public static void resetStoredKey(Context context) {
        context.getApplicationContext()
                .getSharedPreferences("adb_keys", Context.MODE_PRIVATE)
                .edit().clear().commit();
    }

    private static byte[] signAdbToken(byte[] token, RSAPrivateKey privateKey) throws Exception {
        if (token.length != 20) throw new IOException("Unexpected ADB token length: " + token.length);
        Cipher cipher = Cipher.getInstance("RSA/ECB/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, privateKey);
        cipher.update(SIGNATURE_PADDING);
        return cipher.doFinal(token);
    }

    private static byte[] createSignaturePadding() {
        byte[] padding = new byte[236];
        padding[0] = 0x00;
        padding[1] = 0x01;
        int digestStart = padding.length - SHA1_DIGEST_INFO_PREFIX.length;
        for (int i = 2; i < digestStart - 1; i++) padding[i] = (byte) 0xff;
        padding[digestStart - 1] = 0x00;
        System.arraycopy(SHA1_DIGEST_INFO_PREFIX, 0, padding, digestStart,
                SHA1_DIGEST_INFO_PREFIX.length);
        return padding;
    }

    private static byte[] adbPublicKey(RSAPublicKey key) throws Exception {
        final int modulusBytes = 256;
        BigInteger modulus = key.getModulus();
        BigInteger two32 = BigInteger.ONE.shiftLeft(32);
        int modulusWords = modulusBytes / 4;
        BigInteger n0 = modulus.and(two32.subtract(BigInteger.ONE));
        int n0inv = n0.modInverse(two32).negate().intValue();
        BigInteger rr = BigInteger.ONE.shiftLeft(modulusBytes * 8 * 2).mod(modulus);
        byte[] modulusLE = toLittleEndianFixed(modulus, modulusBytes);
        byte[] rrLE = toLittleEndianFixed(rr, modulusBytes);

        ByteBuffer struct = ByteBuffer.allocate(4 + 4 + modulusBytes + modulusBytes + 4)
                .order(ByteOrder.LITTLE_ENDIAN);
        struct.putInt(modulusWords);
        struct.putInt(n0inv);
        struct.put(modulusLE);
        struct.put(rrLE);
        struct.putInt(key.getPublicExponent().intValue());

        String encoded = Base64.encodeToString(struct.array(), Base64.NO_WRAP);
        return (encoded + " fireweb@firetv\0").getBytes("UTF-8");
    }

    private static byte[] toLittleEndianFixed(BigInteger value, int length) throws IOException {
        byte[] src = value.toByteArray();
        int start = (src.length > 1 && src[0] == 0) ? 1 : 0;
        int count = src.length - start;
        if (count > length) throw new IOException("RSA value too large");
        byte[] out = new byte[length];
        for (int i = 0; i < count; i++) out[i] = src[src.length - 1 - i];
        return out;
    }

    private KeyPair loadOrCreateKeyPair() throws Exception {
        SharedPreferences prefs = context.getSharedPreferences("adb_keys", Context.MODE_PRIVATE);
        String privateB64 = prefs.getString("private", null);
        String publicB64 = prefs.getString("public", null);
        KeyFactory factory = KeyFactory.getInstance("RSA");

        if (privateB64 != null && publicB64 != null) {
            try {
                PrivateKey privateKey = factory.generatePrivate(
                        new PKCS8EncodedKeySpec(Base64.decode(privateB64, Base64.DEFAULT)));
                PublicKey publicKey = factory.generatePublic(
                        new X509EncodedKeySpec(Base64.decode(publicB64, Base64.DEFAULT)));
                return new KeyPair(publicKey, privateKey);
            } catch (Exception ignored) {
                prefs.edit().clear().commit();
            }
        }

        KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
        generator.initialize(2048);
        KeyPair kp = generator.generateKeyPair();
        prefs.edit()
                .putString("private", Base64.encodeToString(kp.getPrivate().getEncoded(), Base64.NO_WRAP))
                .putString("public", Base64.encodeToString(kp.getPublic().getEncoded(), Base64.NO_WRAP))
                .commit();
        return kp;
    }

    private static void send(DataOutputStream out, int command, int arg0, int arg1, byte[] data)
            throws IOException {
        int checksum = 0;
        for (byte b : data) checksum += (b & 0xff);
        writeLeInt(out, command);
        writeLeInt(out, arg0);
        writeLeInt(out, arg1);
        writeLeInt(out, data.length);
        writeLeInt(out, checksum);
        writeLeInt(out, command ^ 0xffffffff);
        out.write(data);
        out.flush();
    }

    private static Packet read(DataInputStream in) throws IOException {
        byte[] header = new byte[24];
        in.readFully(header);
        ByteBuffer b = ByteBuffer.wrap(header).order(ByteOrder.LITTLE_ENDIAN);
        Packet p = new Packet();
        p.command = b.getInt();
        p.arg0 = b.getInt();
        p.arg1 = b.getInt();
        int length = b.getInt();
        int checksum = b.getInt();
        int magic = b.getInt();

        if ((p.command ^ 0xffffffff) != magic) throw new IOException("Invalid ADB header");
        if (length < 0 || length > 1024 * 1024)
            throw new IOException("Invalid ADB data length: " + length);

        p.data = new byte[length];
        in.readFully(p.data);
        int actual = 0;
        for (byte value : p.data) actual += (value & 0xff);
        if (actual != checksum) throw new IOException("Invalid ADB checksum");
        return p;
    }

    private static void writeLeInt(DataOutputStream out, int value) throws IOException {
        out.writeByte(value & 0xff);
        out.writeByte((value >>> 8) & 0xff);
        out.writeByte((value >>> 16) & 0xff);
        out.writeByte((value >>> 24) & 0xff);
    }

    private static boolean isNormalClose(Throwable e) {
        Throwable cur = e;
        while (cur != null) {
            String message = cur.getMessage();
            if (message != null) {
                message = message.toLowerCase();
                if (message.contains("broken pipe") ||
                        message.contains("connection reset") ||
                        message.contains("socket closed") ||
                        message.contains("connection abort") ||
                        message.contains("end of stream") ||
                        message.contains("eof")) return true;
            }
            cur = cur.getCause();
        }
        return e instanceof EOFException;
    }

    private static String cleanMessage(Throwable e) {
        if (e == null) return "unknown error";
        String m = e.getMessage();
        return (m == null || m.length() == 0) ? e.getClass().getSimpleName() : m;
    }

    private static String getLanIp() {
        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            String fallback = null;
            for (NetworkInterface nif : Collections.list(interfaces)) {
                if (!nif.isUp() || nif.isLoopback()) continue;
                for (InetAddress addr : Collections.list(nif.getInetAddresses())) {
                    if (!(addr instanceof Inet4Address) || addr.isLoopbackAddress()) continue;
                    String ip = addr.getHostAddress();
                    // Prefer Wi-Fi/Ethernet RFC1918 addresses. Tailscale 100.64/10
                    // should not be selected as the self-ADB target.
                    if (ip.startsWith("192.168.") || ip.startsWith("10.") ||
                            ip.matches("172\\.(1[6-9]|2[0-9]|3[0-1])\\..*")) {
                        if (nif.getName().startsWith("wlan") || nif.getName().startsWith("eth"))
                            return ip;
                        if (fallback == null) fallback = ip;
                    }
                }
            }
            return fallback;
        } catch (Exception ignored) {}
        return null;
    }

    private static class Packet {
        int command;
        int arg0;
        int arg1;
        byte[] data;
    }
}
'''

Path("app/src/main/java/dev/fireweb/remote/AdbClient.java").write_text(adb_client, encoding="utf-8")

adb_manager = r'''package dev.fireweb.remote;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.SystemClock;
import android.util.Log;

public class AdbManager {
    private static final String TAG = "FireWebRemote";
    private static final Object LOCK = new Object();
    private static final String PREFS = "adb_manager";
    private static final String REPAIR_V26 = "repair_v26_done";

    private final Context context;
    private volatile String state = "checking";
    private volatile String lastError = "";
    private volatile long lastSuccessAt = 0L;
    private volatile boolean cleanupDone = false;

    public AdbManager(Context context) {
        this.context = context.getApplicationContext();
    }

    public String getState() { return state; }
    public String getLastError() { return lastError; }

    public void checkAndRepair() {
        synchronized (LOCK) {
            try {
                ensureReadyLocked();
            } catch (Exception e) {
                rememberFailure(e);
            }
        }
    }

    public String shell(String command, int timeoutMs) throws Exception {
        synchronized (LOCK) {
            ensureReadyLocked();

            try {
                String out = new AdbClient(context).shell(command, timeoutMs);
                markReady();
                return out;
            } catch (AdbClient.AdbFailure e) {
                rememberFailure(e);
                if (e.commandMayHaveRun) throw e;

                // Safe transport retry: the shell channel was not accepted yet.
                try { Thread.sleep(180L); } catch (InterruptedException ignored) {}
                String out = new AdbClient(context).shell(command, timeoutMs);
                markReady();
                return out;
            } catch (Exception e) {
                rememberFailure(e);
                throw e;
            }
        }
    }

    private void ensureReadyLocked() throws Exception {
        // A recent successful command is itself a health check.
        if ("ready".equals(state) &&
                SystemClock.elapsedRealtime() - lastSuccessAt < 60000L) return;

        state = "checking";
        Exception first;
        try {
            String result = new AdbClient(context).shell("echo FIREWEB_OK", 9000);
            if (!result.contains("FIREWEB_OK"))
                throw new Exception("ADB health check returned unexpected output");
            markReady();
            cleanupLocked();
            return;
        } catch (Exception e) {
            first = e;
            rememberFailure(e);
        }

        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        boolean repairDone = prefs.getBoolean(REPAIR_V26, false);

        // One controlled identity repair for devices upgraded from the early debug
        // builds. Do not rotate keys repeatedly: once approved, the identity stays.
        if (!repairDone && safeToRepairIdentity(first)) {
            state = "repairing";
            prefs.edit().putBoolean(REPAIR_V26, true).commit();
            AdbClient.resetStoredKey(context);
            try { Thread.sleep(250L); } catch (InterruptedException ignored) {}

            try {
                String result = new AdbClient(context).shell("echo FIREWEB_OK", 12000);
                if (!result.contains("FIREWEB_OK"))
                    throw new Exception("ADB health check returned unexpected output");
                markReady();
                cleanupLocked();
                return;
            } catch (Exception second) {
                rememberFailure(second);
                if (looksLikeAuthorization(second)) {
                    state = "authorization";
                    lastError = "Approve the ADB debugging prompt on Fire TV once";
                }
                throw second;
            }
        }

        if (looksLikeAuthorization(first)) {
            state = "authorization";
            lastError = "Approve the ADB debugging prompt on Fire TV once";
        } else {
            state = "unavailable";
        }
        throw first;
    }

    private void cleanupLocked() {
        if (cleanupDone) return;
        cleanupDone = true;
        try {
            new AdbClient(context).shell(
                    "rm -f /data/local/tmp/FireWeb.apk " +
                    "/data/local/tmp/FireWebRemote-old.apk " +
                    "/data/local/tmp/fireweb-update.log.old 2>/dev/null; true", 7000);
        } catch (Exception e) {
            Log.w(TAG, "ADB cleanup skipped", e);
        }
    }

    private void markReady() {
        state = "ready";
        lastError = "";
        lastSuccessAt = SystemClock.elapsedRealtime();
    }

    private void rememberFailure(Exception e) {
        lastError = message(e);
        if (looksLikeAuthorization(e)) state = "authorization";
        else if (!"repairing".equals(state)) state = "unavailable";
        Log.w(TAG, "ADB manager: " + lastError, e);
    }

    private static boolean safeToRepairIdentity(Exception e) {
        if (e instanceof AdbClient.AdbFailure) {
            AdbClient.AdbFailure f = (AdbClient.AdbFailure)e;
            if (f.commandMayHaveRun) return false;
            return f.stage.contains("authorization") ||
                    f.stage.contains("cnxn") ||
                    f.stage.contains("handshake") ||
                    f.stage.contains("connect") ||
                    f.stage.contains("open");
        }
        String m = message(e).toLowerCase();
        return m.contains("broken pipe") || m.contains("connection reset") ||
                m.contains("authorization") || m.contains("eof") ||
                m.contains("timed out");
    }

    private static boolean looksLikeAuthorization(Exception e) {
        String m = message(e).toLowerCase();
        return m.contains("authorization") || m.contains("approval required") ||
                m.contains("auth-public-key") || m.contains("auth-signature");
    }

    private static String message(Throwable e) {
        if (e == null) return "unknown ADB error";
        String m = e.getMessage();
        return (m == null || m.length() == 0) ? e.getClass().getSimpleName() : m;
    }
}
'''
Path("app/src/main/java/dev/fireweb/remote/AdbManager.java").write_text(adb_manager, encoding="utf-8")

# ---------------------------------------------------------------------------
# FireWebService: use singleton manager, auto-check at startup, expose health,
# and fix the old self-update staging filename mismatch.
# ---------------------------------------------------------------------------
p = Path("app/src/main/java/dev/fireweb/remote/FireWebService.java")
s = p.read_text(encoding="utf-8")

if 'private AdbManager adbManager;' not in s:
    s = s.replace(
        '    private String cachedIndex;\n',
        '    private String cachedIndex;\n    private AdbManager adbManager;\n'
    )

s = s.replace(
    '        startAsForeground();\n        running = true;',
    '        startAsForeground();\n        adbManager = new AdbManager(this);\n        running = true;'
)

startup = '''        new Thread(new Runnable() {
            @Override public void run() { runServer(); }
        }, "fireweb-http").start();'''
startup_new = startup + '''
        pool.execute(new Runnable() {
            @Override public void run() { adbManager.checkAndRepair(); }
        });'''
if startup in s and 'adbManager.checkAndRepair()' not in s:
    s = s.replace(startup, startup_new, 1)

old_adb = '''    private String adb(String command) {
        try {
            String out = new AdbClient(this).shell(command, 20000);
            return out.length() == 0 ? "Done" : out;
        } catch (Exception e) {
            Log.w(TAG, "ADB failed: " + command, e);
            return "ADB unavailable: " + e.getMessage();
        }
    }
'''
new_adb = '''    private String adb(String command) {
        try {
            String out = adbManager.shell(command, 20000);
            return out.length() == 0 ? "Done" : out;
        } catch (Exception e) {
            Log.w(TAG, "ADB failed: " + command, e);
            String state = adbManager == null ? "unavailable" : adbManager.getState();
            String detail = adbManager == null ? e.getMessage() : adbManager.getLastError();
            if (detail == null || detail.length() == 0) detail = e.toString();
            return "ADB " + state + ": " + detail;
        }
    }
'''
if old_adb not in s:
    raise SystemExit("adb() method marker not found for v2.6")
s = s.replace(old_adb, new_adb, 1)

# Add cached ADB health to status JSON without running a new ADB command.
status_marker = '",\\\"sleepTimerRemainingMs\\\":" + sleepTimerRemainingMs() +\n                ",\\\"port\\\":" + PORT +'
status_repl = '",\\\"sleepTimerRemainingMs\\\":" + sleepTimerRemainingMs() +\n                ",\\\"adbState\\\":\\\"" + json(adbManager == null ? "checking" : adbManager.getState()) + "\\\"" +\n                ",\\\"adbError\\\":\\\"" + json(adbManager == null ? "" : adbManager.getLastError()) + "\\\"" +\n                ",\\\"port\\\":" + PORT +'
if status_marker in s:
    s = s.replace(status_marker, status_repl, 1)
else:
    # fallback for builds where sleep-timer patch formatted status differently
    status_marker2 = '",\\\"idleTimeoutMs\\\":" + IDLE_TIMEOUT_MS +\n                ",\\\"port\\\":" + PORT +'
    status_repl2 = '",\\\"idleTimeoutMs\\\":" + IDLE_TIMEOUT_MS +\n                ",\\\"adbState\\\":\\\"" + json(adbManager == null ? "checking" : adbManager.getState()) + "\\\"" +\n                ",\\\"adbError\\\":\\\"" + json(adbManager == null ? "" : adbManager.getLastError()) + "\\\"" +\n                ",\\\"port\\\":" + PORT +'
    if status_marker2 in s:
        s = s.replace(status_marker2, status_repl2, 1)

# The old updater staged FireWebRemote.apk but tried to install FireWeb.apk.
s = s.replace('/data/local/tmp/FireWeb.apk', '/data/local/tmp/FireWebRemote.apk')

p.write_text(s, encoding="utf-8")

# ---------------------------------------------------------------------------
# Web UI: show manager state in the existing top-right status pill. This is
# informational only; no extra ADB polling and no effect on the 90s idle timer.
# ---------------------------------------------------------------------------
p = Path("app/src/main/assets/index.html")
s = p.read_text(encoding="utf-8")

# Extend state object if not already present.
s = s.replace(
    "debugTapCount:0,debugTapAt:0};",
    "debugTapCount:0,debugTapAt:0,adbState:'checking',adbError:''};"
)

# Capture status fields in sync().
s = s.replace(
    "S.sleepTimer=d.sleepTimerRemainingMs||0;renderSleepTimer();$('host').textContent=d.ip+':'+d.port;",
    "S.sleepTimer=d.sleepTimerRemainingMs||0;S.adbState=d.adbState||'checking';S.adbError=d.adbError||'';renderSleepTimer();$('host').textContent=d.ip+':'+d.port;"
)

# Replace the per-second pill text with health-aware output.
s = s.replace(
    "$('state').textContent='Awake · '+Math.ceil(S.remain/1000)+'s';",
    "$('state').textContent=(S.adbState&&S.adbState!=='ready'&&S.adbState!=='checking')?('ADB · '+S.adbState):('Awake · '+Math.ceil(S.remain/1000)+'s');"
)

p.write_text(s, encoding="utf-8")
