from pathlib import Path

java_dir = Path("app/src/main/java/dev/fireweb/remote")

client = r'''package dev.fireweb.remote;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.net.URL;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;

import javax.net.ssl.HostnameVerifier;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSession;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

public class FireLightningClient {
    private static final String PREFS = "fire_lightning";
    private static final String KEY_TOKEN = "client_token";
    private static final String KEY_HOST = "host";
    private static final String API_KEY = "0987654321";

    private final Context context;
    private final SharedPreferences prefs;
    private final SSLContext sslContext;

    public static class PairingRequiredException extends Exception {
        PairingRequiredException(String message) { super(message); }
    }

    public FireLightningClient(Context context) throws Exception {
        this.context = context.getApplicationContext();
        this.prefs = this.context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);

        TrustManager[] trustAll = new TrustManager[]{new X509TrustManager() {
            @Override public java.security.cert.X509Certificate[] getAcceptedIssuers() {
                return new java.security.cert.X509Certificate[0];
            }
            @Override public void checkClientTrusted(java.security.cert.X509Certificate[] c, String a) {}
            @Override public void checkServerTrusted(java.security.cert.X509Certificate[] c, String a) {}
        }};
        sslContext = SSLContext.getInstance("TLS");
        sslContext.init(null, trustAll, new java.security.SecureRandom());
    }

    public boolean isPaired() {
        String token = prefs.getString(KEY_TOKEN, "");
        return token != null && token.length() > 0;
    }

    public synchronized String startPairing() throws Exception {
        Exception last = null;
        for (String host : hosts()) {
            try {
                wakeRemoteApi(host);
                post(host, "/v1/FireTV/pin/display", null,
                        "{\"friendlyName\":\"Fire Control\"}");
                prefs.edit().putString(KEY_HOST, host).apply();
                return "PIN displayed on Fire TV";
            } catch (Exception e) {
                last = e;
            }
        }
        throw last != null ? last : new Exception("Fire TV Remote API unavailable");
    }

    public synchronized String verifyPin(String pin) throws Exception {
        if (pin == null || !pin.matches("[0-9]{4}")) throw new Exception("Enter the 4 digit PIN");
        Exception last = null;
        for (String host : hosts()) {
            try {
                String response = post(host, "/v1/FireTV/pin/verify", null,
                        "{\"pin\":\"" + pin + "\"}");
                JSONObject obj = new JSONObject(response);
                String token = obj.optString("description", "");
                if (token.length() == 0) throw new Exception("No client token returned");
                prefs.edit().putString(KEY_TOKEN, token).putString(KEY_HOST, host).commit();
                return "TV control paired";
            } catch (Exception e) {
                last = e;
            }
        }
        throw last != null ? last : new Exception("PIN verification failed");
    }

    public synchronized String volume(String action) throws Exception {
        String token = prefs.getString(KEY_TOKEN, "");
        if (token == null || token.length() == 0) throw new PairingRequiredException("Pair TV control once");

        String apiAction;
        if ("volup".equals(action)) apiAction = "volume_up";
        else if ("voldown".equals(action)) apiAction = "volume_down";
        else if ("mute".equals(action)) apiAction = "volume_mute";
        else throw new Exception("Unknown volume action");

        Exception last = null;
        for (String host : hosts()) {
            try {
                wakeRemoteApi(host);
                post(host, "/v1/FireTV?action=" + apiAction, token, "{}");
                prefs.edit().putString(KEY_HOST, host).apply();
                if ("volup".equals(action)) return "Volume +";
                if ("voldown".equals(action)) return "Volume -";
                return "Mute";
            } catch (PairingRequiredException e) {
                clearPairing();
                throw e;
            } catch (Exception e) {
                last = e;
            }
        }
        throw last != null ? last : new Exception("TV volume API unavailable");
    }

    public void clearPairing() {
        prefs.edit().remove(KEY_TOKEN).apply();
    }

    private List<String> hosts() {
        ArrayList<String> out = new ArrayList<String>();
        String saved = prefs.getString(KEY_HOST, "");
        String lan = getLanIp();
        if (saved != null && saved.length() > 0) out.add(saved);
        if (lan != null && lan.length() > 0 && !out.contains(lan)) out.add(lan);
        if (!out.contains("127.0.0.1")) out.add("127.0.0.1");
        return out;
    }

    private void wakeRemoteApi(String host) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL("http://" + host + ":8009/apps/FireTVRemote");
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(1200);
            conn.setReadTimeout(1200);
            conn.setDoOutput(true);
            conn.getOutputStream().close();
            conn.getResponseCode();
        } catch (Exception ignored) {
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private String post(String host, String path, String token, String body) throws Exception {
        HttpsURLConnection conn = null;
        try {
            URL url = new URL("https://" + host + ":8080" + path);
            conn = (HttpsURLConnection) url.openConnection();
            conn.setSSLSocketFactory(sslContext.getSocketFactory());
            conn.setHostnameVerifier(new HostnameVerifier() {
                @Override public boolean verify(String h, SSLSession s) { return true; }
            });
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(3000);
            conn.setReadTimeout(5000);
            conn.setDoOutput(true);
            conn.setRequestProperty("X-Api-Key", API_KEY);
            if (token != null && token.length() > 0) conn.setRequestProperty("X-Client-Token", token);
            conn.setRequestProperty("User-Agent", "okhttp/4.10.0");
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");

            byte[] bytes = (body == null ? "{}" : body).getBytes("UTF-8");
            conn.setFixedLengthStreamingMode(bytes.length);
            OutputStream out = conn.getOutputStream();
            out.write(bytes);
            out.flush();
            out.close();

            int code = conn.getResponseCode();
            if (code == 401 || code == 403) throw new PairingRequiredException("TV control token expired");
            InputStream in = code >= 200 && code < 400 ? conn.getInputStream() : conn.getErrorStream();
            String response = readAll(in);
            if (code < 200 || code >= 300) throw new Exception("Fire TV API HTTP " + code + (response.length() > 0 ? ": " + response : ""));
            return response;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private static String readAll(InputStream in) throws Exception {
        if (in == null) return "";
        BufferedReader reader = new BufferedReader(new InputStreamReader(in, "UTF-8"));
        StringBuilder out = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) out.append(line);
        reader.close();
        return out.toString();
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
                    if (ip.startsWith("192.168.") || ip.startsWith("10.") ||
                            ip.matches("172\\.(1[6-9]|2[0-9]|3[0-1])\\..*")) {
                        if (nif.getName().startsWith("wlan") || nif.getName().startsWith("eth")) return ip;
                        if (fallback == null) fallback = ip;
                    }
                }
            }
            return fallback;
        } catch (Exception ignored) {}
        return null;
    }
}
'''
(java_dir / "FireLightningClient.java").write_text(client, encoding="utf-8")

# Backend integration ---------------------------------------------------------
p = java_dir / "FireWebService.java"
s = p.read_text(encoding="utf-8")

if 'private FireLightningClient lightningClient;' not in s:
    s = s.replace('    private AdbManager adbManager;\n',
                  '    private AdbManager adbManager;\n    private FireLightningClient lightningClient;\n')

s = s.replace(
    '        adbManager = new AdbManager(this);\n        ensureNativeControl();',
    '        adbManager = new AdbManager(this);\n        try { lightningClient = new FireLightningClient(this); } catch (Exception e) { Log.w(TAG, "Lightning init failed", e); }\n        ensureNativeControl();'
)

# Pairing route, after keepalive and before apps.
route_marker = '''        if ("/api/apps".equals(path)) {
            markActive();
            return jsonResponse(appsJson());
        }
'''
pair_route = '''        if ("/api/tv-control".equals(path)) {
            markActive();
            String action = param(query, "action");
            try {
                if (lightningClient == null) throw new Exception("TV control API unavailable");
                if ("start".equals(action)) {
                    String msg = lightningClient.startPairing();
                    return jsonResponse("{\\\"ok\\\":true,\\\"pairing\\\":true,\\\"message\\\":\\\"" + json(msg) + "\\\"}");
                }
                if ("verify".equals(action)) {
                    String pin = param(query, "pin");
                    String msg = lightningClient.verifyPin(pin);
                    return jsonResponse("{\\\"ok\\\":true,\\\"paired\\\":true,\\\"message\\\":\\\"" + json(msg) + "\\\"}");
                }
                if ("reset".equals(action)) {
                    lightningClient.clearPairing();
                    return jsonResponse("{\\\"ok\\\":true,\\\"paired\\\":false,\\\"message\\\":\\\"TV control pairing reset\\\"}");
                }
                return jsonResponse("{\\\"ok\\\":true,\\\"paired\\\":" + lightningClient.isPaired() + "}");
            } catch (Exception e) {
                return textResponse(500, "application/json; charset=utf-8",
                        "{\\\"ok\\\":false,\\\"error\\\":\\\"" + json(e.getMessage() == null ? e.toString() : e.getMessage()) + "\\\"}");
            }
        }

'''
if route_marker not in s:
    raise SystemExit("v2.9 volume route marker not found")
s = s.replace(route_marker, pair_route + route_marker, 1)

# Replace v2.8 AudioManager volume block with Lightning remote API.
start = s.find('    private String nativeRemote(String key) {')
if start < 0:
    raise SystemExit("nativeRemote not found")
vol_start = s.find('        if ("volup".equals(key) || "voldown".equals(key) || "mute".equals(key)) {', start)
ensure = s.find('        ensureNativeControl();', vol_start)
if vol_start < 0 or ensure < 0:
    raise SystemExit("v2.8 volume block not found")
new_vol = '''        if ("volup".equals(key) || "voldown".equals(key) || "mute".equals(key)) {
            try {
                if (lightningClient == null || !lightningClient.isPaired()) return "TV_PAIR_REQUIRED";
                return lightningClient.volume(key);
            } catch (FireLightningClient.PairingRequiredException e) {
                return "TV_PAIR_REQUIRED";
            } catch (Throwable e) {
                return "TV volume failed: " + (e.getMessage() == null ? e.toString() : e.getMessage());
            }
        }

'''
s = s[:vol_start] + new_vol + s[ensure:]
p.write_text(s, encoding="utf-8")

# Web pairing UI --------------------------------------------------------------
p = Path("app/src/main/assets/index.html")
s = p.read_text(encoding="utf-8")

pair_css = r'''
.pairShade{position:fixed;inset:0;z-index:45;display:none;place-items:center;padding:20px;background:#000b;backdrop-filter:blur(8px)}.pairShade.on{display:grid}.pairBox{width:min(340px,100%);padding:16px;border:1px solid var(--cli-line,var(--line));border-radius:10px;background:#050806f6;box-shadow:0 20px 70px #000}.pairTitle{font-size:11px;font-weight:800;color:var(--cli-accent,#fff);letter-spacing:.05em}.pairText{margin:8px 0 12px;color:var(--cli-muted,#999);font-size:9px;line-height:1.5}.pairRow{display:grid;grid-template-columns:minmax(0,1fr) 90px;gap:7px}.pairPin{min-width:0;height:42px;border:1px solid var(--cli-line,var(--line));border-radius:8px;background:#020403;color:var(--cli-text,#fff);font:700 18px ui-monospace,monospace;text-align:center;letter-spacing:.28em;outline:none}.pairGo{border:1px solid var(--cli-accent,#fff);border-radius:8px;background:var(--cli-accent,#fff);color:#041006;font:800 9px ui-monospace,monospace}.pairCancel{width:100%;margin-top:7px;height:30px;border:1px solid var(--cli-line,var(--line));border-radius:7px;background:transparent;color:var(--cli-muted,#999);font:700 8px ui-monospace,monospace}body.pinkTheme .pairBox{background:#0d050bf6}body.pinkTheme .pairPin{background:#070306;color:var(--cli-text)}body.pinkTheme .pairGo{color:#210416}
'''
s = s.replace('</style>', pair_css + '\n</style>', 1)

pair_html = '''<div id="tvPairShade" class="pairShade"><div class="pairBox"><div class="pairTitle">[TV_CONTROL // PAIR]</div><div class="pairText">A 4-digit PIN is now shown on the Fire TV. Enter it once. The token is stored on the Fire TV and shared by every browser.</div><div class="pairRow"><input id="tvPairPin" class="pairPin" inputmode="numeric" maxlength="4" pattern="[0-9]*" autocomplete="one-time-code"><button id="tvPairGo" class="pairGo">PAIR</button></div><button id="tvPairCancel" class="pairCancel">CANCEL</button></div></div>\n'''
s = s.replace('<div id="toast" class="toast"></div>', pair_html + '<div id="toast" class="toast"></div>', 1)

# Extend state.
s = s.replace("remoteMode:(localStorage.getItem('remoteMode')||'buttons'),standalone:false};",
              "remoteMode:(localStorage.getItem('remoteMode')||'buttons'),standalone:false,pendingVolumeKey:null,tvPairStarting:false};")

old_remote_js = "async function remote(key){try{const d=await api('/api/remote?key='+encodeURIComponent(key));S.remain=90000;toast(d.message||key)}catch(e){toast(e.message)}}"
new_remote_js = r'''async function remote(key){try{const d=await api('/api/remote?key='+encodeURIComponent(key));S.remain=90000;if(d.message==='TV_PAIR_REQUIRED'){S.pendingVolumeKey=key;await beginTvPair();return}toast(d.message||key)}catch(e){toast(e.message)}}
async function beginTvPair(){if(S.tvPairStarting)return;S.tvPairStarting=true;try{toast('Starting TV control pairing…');await api('/api/tv-control?action=start');$('tvPairPin').value='';$('tvPairShade').classList.add('on');setTimeout(()=>$('tvPairPin').focus(),120)}catch(e){toast(e.message)}finally{S.tvPairStarting=false}}
async function verifyTvPair(){const pin=$('tvPairPin').value.replace(/\D/g,'').slice(0,4);if(pin.length!==4){toast('Enter the 4 digit PIN');return}try{const d=await api('/api/tv-control?action=verify&pin='+encodeURIComponent(pin));$('tvPairShade').classList.remove('on');toast(d.message||'TV control paired');const key=S.pendingVolumeKey;S.pendingVolumeKey=null;if(key)setTimeout(()=>remote(key),250)}catch(e){toast(e.message)}}
'''
if old_remote_js not in s:
    raise SystemExit("v2.9 volume remote JS marker not found")
s = s.replace(old_remote_js, new_remote_js, 1)

listener_marker = "$('remoteModeBtn').onclick=toggleRemoteMode;"
listener_repl = "$('tvPairGo').onclick=verifyTvPair;$('tvPairCancel').onclick=()=>{$('tvPairShade').classList.remove('on');S.pendingVolumeKey=null};$('tvPairPin').addEventListener('keydown',e=>{if(e.key==='Enter')verifyTvPair()});" + listener_marker
if listener_marker not in s:
    raise SystemExit("v2.9 volume mode listener marker not found")
s = s.replace(listener_marker, listener_repl, 1)

p.write_text(s, encoding="utf-8")
