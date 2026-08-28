package dev.fireweb.remote;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.Log;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.io.BufferedWriter;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.NetworkInterface;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URLDecoder;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.Comparator;
import java.util.Enumeration;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class FireWebService extends Service {
    private static final String TAG = "FireWebRemote";
    private static final int PORT = 8765;
    private static final int NOTIFICATION_ID = 8765;
    private static final String CHANNEL_ID = "fireweb_remote";
    private static final long IDLE_TIMEOUT_MS = 30_000L;
    private static final String UPDATE_URL = "https://raw.githubusercontent.com/Amoo71/02/main/dist/FireWebRemote.apk";

    private volatile long lastActiveAt = SystemClock.elapsedRealtime();
    private volatile boolean running;
    private ServerSocket serverSocket;
    private final ExecutorService pool = Executors.newFixedThreadPool(3);
    private final Map<String, byte[]> iconCache = new ConcurrentHashMap<String, byte[]>();
    private String cachedIndex;

    @Override
    public void onCreate() {
        super.onCreate();
        startAsForeground();
        running = true;
        new Thread(new Runnable() {
            @Override public void run() { runServer(); }
        }, "fireweb-http").start();
    }

    private void startAsForeground() {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID, "Fire Web Remote", NotificationManager.IMPORTANCE_MIN);
            channel.setDescription("Local Fire TV web remote");
            channel.setSound(null, null);
            channel.enableVibration(false);
            nm.createNotificationChannel(channel);
        }

        Intent openIntent = new Intent(this, MainActivity.class);
        int piFlags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= 23) piFlags |= PendingIntent.FLAG_IMMUTABLE;
        PendingIntent pi = PendingIntent.getActivity(this, 0, openIntent, piFlags);
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        Notification n = builder
                .setContentTitle("Fire Web Remote")
                .setContentText("Listening on port " + PORT)
                .setSmallIcon(android.R.drawable.ic_menu_view)
                .setContentIntent(pi)
                .setOngoing(true)
                .setShowWhen(false)
                .build();
        startForeground(NOTIFICATION_ID, n);
    }

    private void runServer() {
        while (running) {
            try {
                serverSocket = new ServerSocket();
                serverSocket.setReuseAddress(true);
                serverSocket.bind(new InetSocketAddress(PORT));
                while (running) {
                    final Socket client = serverSocket.accept();
                    client.setSoTimeout(12000);
                    pool.execute(new Runnable() {
                        @Override public void run() { handleClient(client); }
                    });
                }
            } catch (Exception e) {
                if (running) Log.e(TAG, "HTTP server error", e);
                closeServer();
                if (running) try { Thread.sleep(2000); } catch (InterruptedException ignored) {}
            }
        }
    }

    private void handleClient(Socket socket) {
        try {
            BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), "UTF-8"));
            String first = reader.readLine();
            if (first == null) return;
            String target = "/";
            String[] parts = first.split(" ");
            if (parts.length >= 2) target = parts[1];
            String line;
            while ((line = reader.readLine()) != null && line.length() > 0) {}

            String path = target;
            String query = "";
            int q = target.indexOf('?');
            if (q >= 0) {
                path = target.substring(0, q);
                query = target.substring(q + 1);
            }
            writeResponse(socket, route(path, query));
        } catch (Exception e) {
            Log.w(TAG, "Client error", e);
        } finally {
            try { socket.close(); } catch (Exception ignored) {}
        }
    }

    private Response route(String path, String query) {
        if ("/".equals(path) || "/index.html".equals(path)) {
            return textResponse(200, "text/html; charset=utf-8", loadIndex());
        }
        if ("/api/status".equals(path)) return jsonResponse(statusJson());
        if ("/api/wake".equals(path)) return jsonResponse(wakeJson());

        if (isIdle()) {
            return textResponse(423, "application/json; charset=utf-8",
                    "{\"ok\":false,\"idle\":true,\"error\":\"Device is in Ultra Idle. Wake it first.\"}");
        }

        if ("/api/keepalive".equals(path)) {
            markActive();
            return jsonResponse("{\"ok\":true,\"remainingMs\":" + IDLE_TIMEOUT_MS + "}");
        }

        if ("/api/apps".equals(path)) {
            markActive();
            return jsonResponse(appsJson());
        }

        if ("/api/icon".equals(path)) {
            markActive();
            String pkg = param(query, "package");
            if (!isSafePackage(pkg)) return badRequest("Invalid package name");
            return iconResponse(pkg);
        }

        if ("/api/action".equals(path)) {
            markActive();
            String type = param(query, "type");
            String pkg = param(query, "package");
            if (!isSafePackage(pkg)) return badRequest("Invalid package name");
            if ("launch".equals(type)) return jsonResponse(resultJson("Launch", adb("monkey -p " + pkg + " 1")));
            if ("force-stop".equals(type)) return jsonResponse(resultJson("Force stop", adb("am force-stop " + pkg)));
            return badRequest("Unknown action");
        }

        if ("/api/remote".equals(path)) {
            markActive();
            String key = param(query, "key");
            int code = keyCode(key);
            if (code < 0) return badRequest("Unknown remote key");
            return jsonResponse(resultJson("Remote", adb("input keyevent " + code)));
        }

        if ("/api/update".equals(path)) {
            markActive();
            return jsonResponse(updateJson());
        }

        if ("/api/tool".equals(path)) {
            markActive();
            String type = param(query, "type");
            if ("kill-background".equals(type)) return jsonResponse(resultJson("Clean background", adb("am kill-all")));
            if ("trim-cache".equals(type)) return jsonResponse(resultJson("Trim caches", adb("pm trim-caches 999999999999"));
            if ("sleep".equals(type)) {
                String r = adb("input keyevent 223");
                forceIdle();
                return jsonResponse(resultJson("Sleep", r));
            }
            return badRequest("Unknown tool");
        }

        return textResponse(404, "application/json; charset=utf-8", "{\"ok\":false,\"error\":\"Not found\"}");
    }

    private int keyCode(String key) {
        if ("up".equals(key)) return 19;
        if ("down".equals(key)) return 20;
        if ("left".equals(key)) return 21;
        if ("right".equals(key)) return 22;
        if ("ok".equals(key)) return 23;
        if ("home".equals(key)) return 3;
        if ("back".equals(key)) return 4;
        if ("menu".equals(key)) return 82;
        if ("volup".equals(key)) return 24;
        if ("voldown".equals(key)) return 25;
        if ("mute".equals(key)) return 164;
        return -1;
    }

    private String statusJson() {
        return "{\"ok\":true,\"idle\":" + isIdle() +
                ",\"remainingMs\":" + remainingActiveMs() +
                ",\"idleTimeoutMs\":" + IDLE_TIMEOUT_MS +
                ",\"port\":" + PORT +
                ",\"ip\":\"" + json(getLanIp()) + "\"}";
    }

    private String wakeJson() {
        markActive();
        try {
            PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
            if (pm != null) {
                PowerManager.WakeLock lock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "FireWebRemote:wake");
                lock.acquire(5000);
            }
        } catch (Exception e) {
            Log.w(TAG, "Wake lock failed", e);
        }
        String wake = adb("input keyevent 224");
        return "{\"ok\":true,\"idle\":false,\"message\":\"Awake\",\"adb\":\"" +
                json(wake) + "\",\"remainingMs\":" + IDLE_TIMEOUT_MS + "}";
    }

    private String appsJson() {
        try {
            final PackageManager pm = getPackageManager();
            List<ApplicationInfo> apps = pm.getInstalledApplications(PackageManager.GET_META_DATA);
            Collections.sort(apps, new Comparator<ApplicationInfo>() {
                @Override public int compare(ApplicationInfo a, ApplicationInfo b) {
                    return label(pm, a).compareToIgnoreCase(label(pm, b));
                }
            });
            StringBuilder out = new StringBuilder(32768);
            out.append("{\"ok\":true,\"apps\":[");
            boolean first = true;
            for (ApplicationInfo app : apps) {
                if (!first) out.append(',');
                first = false;
                boolean system = (app.flags & ApplicationInfo.FLAG_SYSTEM) != 0 ||
                        (app.flags & ApplicationInfo.FLAG_UPDATED_SYSTEM_APP) != 0;
                boolean launchable = pm.getLaunchIntentForPackage(app.packageName) != null;
                out.append("{\"name\":\"").append(json(label(pm, app)))
                        .append("\",\"package\":\"").append(json(app.packageName))
                        .append("\",\"system\":").append(system)
                        .append(",\"launchable\":").append(launchable).append('}');
            }
            return out.append("]}").toString();
        } catch (Exception e) {
            return "{\"ok\":false,\"error\":\"" + json(e.toString()) + "\",\"apps\":[]}";
        }
    }

    private Response iconResponse(String pkg) {
        try {
            byte[] cached = iconCache.get(pkg);
            if (cached != null) return new Response(200, "image/png", cached);

            PackageManager pm = getPackageManager();
            Drawable drawable = pm.getApplicationIcon(pkg);
            int size = 96;
            Bitmap bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
            Canvas canvas = new Canvas(bitmap);
            drawable.setBounds(0, 0, size, size);
            drawable.draw(canvas);
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            bitmap.compress(Bitmap.CompressFormat.PNG, 92, out);
            bitmap.recycle();
            byte[] data = out.toByteArray();
            if (data.length > 0) iconCache.put(pkg, data);
            return new Response(200, "image/png", data);
        } catch (Exception e) {
            return textResponse(404, "text/plain; charset=utf-8", "icon unavailable");
        }
    }

    private String updateJson() {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(UPDATE_URL + "?t=" + System.currentTimeMillis());
            conn = (HttpURLConnection) url.openConnection();
            conn.setInstanceFollowRedirects(true);
            conn.setConnectTimeout(12000);
            conn.setReadTimeout(30000);
            conn.setRequestProperty("User-Agent", "FireWebRemote/2.1");
            int code = conn.getResponseCode();
            if (code < 200 || code >= 300) {
                return "{\"ok\":false,\"error\":\"Download failed: HTTP " + code + "\"}";
            }

            File update = new File(getFilesDir(), "update.apk");
            InputStream in = conn.getInputStream();
            FileOutputStream fos = new FileOutputStream(update, false);
            byte[] buf = new byte[8192];
            long total = 0;
            int n;
            while ((n = in.read(buf)) > 0) {
                fos.write(buf, 0, n);
                total += n;
                if (total > 20L * 1024L * 1024L) throw new Exception("APK too large");
            }
            fos.flush();
            fos.close();
            in.close();

            if (total < 12000) throw new Exception("Downloaded APK is too small");
            FileInputStream check = new FileInputStream(update);
            int p = check.read();
            int k = check.read();
            check.close();
            if (p != 'P' || k != 'K') throw new Exception("Downloaded file is not an APK");

            String staged = adb("run-as dev.fireweb.remote cat files/update.apk > /data/local/tmp/FireWebRemote.apk && echo STAGED");
            if (!staged.contains("STAGED")) throw new Exception("Could not stage APK: " + staged);

            // Preserve the local ADB RSA key in case Android requires a full uninstall
            // because a GitHub debug build was signed with a different ephemeral key.
            adb("run-as dev.fireweb.remote cat shared_prefs/adb_keys.xml > /data/local/tmp/fireweb-adb-keys.xml 2>/dev/null; true");

            String script =
                    ("sleep 3; " +
                    "if pm install -r /data/local/tmp/FireWeb.apk; then " +
                    "  am start -n dev.fireweb.remote/.MainActivity; " +
                    "else " +
                    "  pm uninstall dev.fireweb.remote; " +
                    "  pm install /data/local/tmp/FireWeb.apk; " +
                    "  run-as dev.fireweb.remote mkdir -p shared_prefs; " +
                    "  if [ -s /data/local/tmp/fireweb-adb-keys.xml ]; then " +
                    "    cat /data/local/tmp/fireweb-adb-keys.xml | run-as dev.fireweb.remote sh -c 'cat > shared_prefs/adb_keys.xml'; " +
                    "  fi; " +
                    "  am start -n dev.fireweb.remote/.MainActivity; " +
                    "fi) >/data/local/tmp/fireweb-update.log 2>&1 &";
            adb(script);

            return "{\"ok\":true,\"message\":\"Update downloaded. Fire Control will restart in a few seconds.\",\"restarting\":true}";
        } catch (Exception e) {
            return "{\"ok\":false,\"error\":\"" + json(e.getMessage() == null ? e.toString() : e.getMessage()) + "\"}";
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private static String label(PackageManager pm, ApplicationInfo app) {
        try {
            CharSequence c = pm.getApplicationLabel(app);
            if (c != null && c.length() > 0) return c.toString();
        } catch (Exception ignored) {}
        return app.packageName;
    }

    private String adb(String command) {
        try {
            String out = new AdbClient(this).shell(command, 20000);
            return out.length() == 0 ? "Done" : out;
        } catch (Exception e) {
            Log.w(TAG, "ADB failed: " + command, e);
            return "ADB unavailable: " + e.getMessage();
        }
    }

    private String loadIndex() {
        if (cachedIndex != null) return cachedIndex;
        try {
            InputStream in = getAssets().open("index.html");
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            int n;
            while ((n = in.read(buffer)) >= 0) out.write(buffer, 0, n);
            in.close();
            cachedIndex = new String(out.toByteArray(), "UTF-8");
            return cachedIndex;
        } catch (Exception e) {
            return "<!doctype html><meta name=viewport content='width=device-width'><body style='background:#111;color:white;font-family:sans-serif'>UI asset missing</body>";
        }
    }

    private void writeResponse(Socket socket, Response response) throws Exception {
        BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(socket.getOutputStream(), "UTF-8"));
        writer.write("HTTP/1.1 " + response.status + " " + statusText(response.status) + "\r\n");
        writer.write("Content-Type: " + response.contentType + "\r\n");
        writer.write("Content-Length: " + response.body.length + "\r\n");
        writer.write("Cache-Control: no-store, no-cache, must-revalidate\r\n");
        writer.write("Pragma: no-cache\r\nConnection: close\r\nX-Content-Type-Options: nosniff\r\n\r\n");
        writer.flush();
        socket.getOutputStream().write(response.body);
        socket.getOutputStream().flush();
    }

    private boolean isIdle() { return SystemClock.elapsedRealtime() - lastActiveAt >= IDLE_TIMEOUT_MS; }
    private long remainingActiveMs() { return Math.max(0L, IDLE_TIMEOUT_MS - (SystemClock.elapsedRealtime() - lastActiveAt)); }
    private void markActive() { lastActiveAt = SystemClock.elapsedRealtime(); }
    private void forceIdle() { lastActiveAt = SystemClock.elapsedRealtime() - IDLE_TIMEOUT_MS; }

    private String resultJson(String action, String message) {
        return "{\"ok\":true,\"action\":\"" + json(action) + "\",\"message\":\"" + json(message) +
                "\",\"remainingMs\":" + remainingActiveMs() + "}";
    }

    private static boolean isSafePackage(String pkg) {
        return pkg != null && pkg.matches("[A-Za-z0-9_]+(?:\\.[A-Za-z0-9_]+)+");
    }

    private static String param(String query, String key) {
        if (query == null || query.length() == 0) return "";
        for (String pair : query.split("&")) {
            int eq = pair.indexOf('=');
            String k = eq >= 0 ? pair.substring(0, eq) : pair;
            if (key.equals(urlDecode(k))) return eq >= 0 ? urlDecode(pair.substring(eq + 1)) : "";
        }
        return "";
    }

    private static String urlDecode(String s) {
        try { return URLDecoder.decode(s, "UTF-8"); } catch (Exception e) { return s; }
    }

    private static Response jsonResponse(String body) { return textResponse(200, "application/json; charset=utf-8", body); }
    private static Response badRequest(String message) {
        return textResponse(400, "application/json; charset=utf-8", "{\"ok\":false,\"error\":\"" + json(message) + "\"}");
    }
    private static Response textResponse(int status, String contentType, String body) {
        return new Response(status, contentType, body.getBytes(StandardCharsets.UTF_8));
    }

    private static String statusText(int status) {
        if (status == 200) return "OK";
        if (status == 400) return "Bad Request";
        if (status == 404) return "Not Found";
        if (status == 423) return "Locked";
        return "Error";
    }

    private String getLanIp() {
        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            for (NetworkInterface nif : Collections.list(interfaces)) {
                if (!nif.isUp() || nif.isLoopback()) continue;
                for (InetAddress addr : Collections.list(nif.getInetAddresses())) {
                    if (addr instanceof Inet4Address && !addr.isLoopbackAddress() && addr.isSiteLocalAddress()) {
                        return addr.getHostAddress();
                    }
                }
            }
        } catch (Exception ignored) {}
        return "FIRE-TV-IP";
    }

    private static String json(String s) {
        if (s == null) return "";
        StringBuilder out = new StringBuilder(s.length() + 16);
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': out.append("\\\\"); break;
                case '"': out.append("\\\""); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                default:
                    if (c < 0x20) out.append(String.format(Locale.US, "\\u%04x", (int) c));
                    else out.append(c);
            }
        }
        return out.toString();
    }

    private void closeServer() { try { if (serverSocket != null) serverSocket.close(); } catch (Exception ignored) {} }

    @Override public int onStartCommand(Intent intent, int flags, int startId) { return START_STICKY; }
    @Override public void onDestroy() { running = false; closeServer(); pool.shutdownNow(); super.onDestroy(); }
    @Override public IBinder onBind(Intent intent) { return null; }

    private static class Response {
        final int status;
        final String contentType;
        final byte[] body;
        Response(int status, String contentType, byte[] body) {
            this.status = status;
            this.contentType = contentType;
            this.body = body;
        }
    }
}
