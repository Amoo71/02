from pathlib import Path
import re

# ---------------------------------------------------------------------------
# v2.8: Stop depending on Fire TV connecting back into its own adbd.
# Main control path becomes native Android APIs + AccessibilityService.
# One-time shell bootstrap grants WRITE_SECURE_SETTINGS and activates Device Admin.
# ---------------------------------------------------------------------------

java_dir = Path("app/src/main/java/dev/fireweb/remote")
xml_dir = Path("app/src/main/res/xml")
xml_dir.mkdir(parents=True, exist_ok=True)

accessibility = r'''package dev.fireweb.remote;

import android.accessibilityservice.AccessibilityService;
import android.view.View;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

public class FireAccessibilityService extends AccessibilityService {
    private static volatile FireAccessibilityService instance;

    public static FireAccessibilityService getInstance() {
        return instance;
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
    }

    @Override
    public boolean onUnbind(android.content.Intent intent) {
        if (instance == this) instance = null;
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        if (instance == this) instance = null;
        super.onDestroy();
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {}

    @Override
    public void onInterrupt() {}

    public String command(String key) {
        if ("home".equals(key)) {
            return performGlobalAction(GLOBAL_ACTION_HOME) ? "Home" : "Home unavailable";
        }
        if ("back".equals(key)) {
            return performGlobalAction(GLOBAL_ACTION_BACK) ? "Back" : "Back unavailable";
        }
        if ("up".equals(key)) return moveFocus(View.FOCUS_UP) ? "Up" : "No focus target";
        if ("down".equals(key)) return moveFocus(View.FOCUS_DOWN) ? "Down" : "No focus target";
        if ("left".equals(key)) return moveFocus(View.FOCUS_LEFT) ? "Left" : "No focus target";
        if ("right".equals(key)) return moveFocus(View.FOCUS_RIGHT) ? "Right" : "No focus target";
        if ("ok".equals(key)) return clickFocused() ? "OK" : "Nothing clickable";
        if ("menu".equals(key)) return longClickFocused() ? "Menu" : "Menu unavailable on this screen";
        return "Unknown key";
    }

    private AccessibilityNodeInfo focusedNode(AccessibilityNodeInfo root) {
        if (root == null) return null;
        AccessibilityNodeInfo node = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
        if (node == null) node = root.findFocus(AccessibilityNodeInfo.FOCUS_ACCESSIBILITY);
        return node;
    }

    private boolean moveFocus(int direction) {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return false;
        AccessibilityNodeInfo current = null;
        AccessibilityNodeInfo next = null;
        try {
            current = focusedNode(root);
            if (current == null) return focusFirst(root);
            next = current.focusSearch(direction);
            if (next == null) return false;
            boolean a = next.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            boolean b = next.performAction(AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS);
            return a || b;
        } catch (Throwable ignored) {
            return false;
        } finally {
            if (next != null) try { next.recycle(); } catch (Throwable ignored) {}
            if (current != null) try { current.recycle(); } catch (Throwable ignored) {}
            try { root.recycle(); } catch (Throwable ignored) {}
        }
    }

    private boolean focusFirst(AccessibilityNodeInfo root) {
        for (int i = 0; i < root.getChildCount(); i++) {
            AccessibilityNodeInfo child = root.getChild(i);
            if (child == null) continue;
            try {
                if (child.isFocusable() && child.isVisibleToUser()) {
                    boolean a = child.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
                    boolean b = child.performAction(AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS);
                    if (a || b) return true;
                }
                if (focusFirst(child)) return true;
            } finally {
                try { child.recycle(); } catch (Throwable ignored) {}
            }
        }
        return false;
    }

    private boolean clickFocused() {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return false;
        AccessibilityNodeInfo node = null;
        try {
            node = focusedNode(root);
            if (node == null) return false;
            AccessibilityNodeInfo cur = node;
            while (cur != null) {
                if (cur.isClickable() && cur.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true;
                AccessibilityNodeInfo parent = cur.getParent();
                if (cur != node) try { cur.recycle(); } catch (Throwable ignored) {}
                cur = parent;
            }
            return node.performAction(AccessibilityNodeInfo.ACTION_SELECT);
        } catch (Throwable ignored) {
            return false;
        } finally {
            if (node != null) try { node.recycle(); } catch (Throwable ignored) {}
            try { root.recycle(); } catch (Throwable ignored) {}
        }
    }

    private boolean longClickFocused() {
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return false;
        AccessibilityNodeInfo node = null;
        try {
            node = focusedNode(root);
            if (node == null) return false;
            AccessibilityNodeInfo cur = node;
            while (cur != null) {
                if (cur.isLongClickable() && cur.performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK)) return true;
                AccessibilityNodeInfo parent = cur.getParent();
                if (cur != node) try { cur.recycle(); } catch (Throwable ignored) {}
                cur = parent;
            }
            return false;
        } catch (Throwable ignored) {
            return false;
        } finally {
            if (node != null) try { node.recycle(); } catch (Throwable ignored) {}
            try { root.recycle(); } catch (Throwable ignored) {}
        }
    }
}
'''
(java_dir / "FireAccessibilityService.java").write_text(accessibility, encoding="utf-8")

device_admin = r'''package dev.fireweb.remote;

import android.app.admin.DeviceAdminReceiver;

public class FireDeviceAdminReceiver extends DeviceAdminReceiver {}
'''
(java_dir / "FireDeviceAdminReceiver.java").write_text(device_admin, encoding="utf-8")

(xml_dir / "fire_accessibility_service.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:accessibilityEventTypes="typeWindowStateChanged|typeWindowContentChanged|typeViewFocused|typeViewAccessibilityFocused"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:notificationTimeout="50"
    android:canRetrieveWindowContent="true"
    android:accessibilityFlags="flagReportViewIds|flagRetrieveInteractiveWindows" />
''', encoding="utf-8")

(xml_dir / "device_admin.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<device-admin xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-policies>
        <force-lock />
    </uses-policies>
</device-admin>
''', encoding="utf-8")

# ---- Manifest --------------------------------------------------------------
p = Path("app/src/main/AndroidManifest.xml")
s = p.read_text(encoding="utf-8")
if 'android.permission.WRITE_SECURE_SETTINGS' not in s:
    s = s.replace(
        '    <uses-permission android:name="android.permission.WAKE_LOCK" />\n',
        '    <uses-permission android:name="android.permission.WAKE_LOCK" />\n'
        '    <uses-permission android:name="android.permission.WRITE_SECURE_SETTINGS" />\n'
        '    <uses-permission android:name="android.permission.KILL_BACKGROUND_PROCESSES" />\n'
    )

insert = r'''
        <service
            android:name=".FireAccessibilityService"
            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
            android:exported="true">
            <intent-filter>
                <action android:name="android.accessibilityservice.AccessibilityService" />
            </intent-filter>
            <meta-data
                android:name="android.accessibilityservice"
                android:resource="@xml/fire_accessibility_service" />
        </service>

        <receiver
            android:name=".FireDeviceAdminReceiver"
            android:permission="android.permission.BIND_DEVICE_ADMIN"
            android:exported="true">
            <meta-data
                android:name="android.app.device_admin"
                android:resource="@xml/device_admin" />
            <intent-filter>
                <action android:name="android.app.action.DEVICE_ADMIN_ENABLED" />
            </intent-filter>
        </receiver>
'''
if '.FireAccessibilityService' not in s:
    s = s.replace('        <receiver\n            android:name=".BootReceiver"', insert + '\n        <receiver\n            android:name=".BootReceiver"')
p.write_text(s, encoding="utf-8")

# ---- FireWebService ---------------------------------------------------------
p = java_dir / "FireWebService.java"
s = p.read_text(encoding="utf-8")

# Imports.
s = s.replace('import android.app.Service;\n', 'import android.app.Service;\nimport android.app.ActivityManager;\nimport android.app.admin.DevicePolicyManager;\n')
s = s.replace('import android.content.Intent;\n', 'import android.content.Intent;\nimport android.content.ComponentName;\n')
s = s.replace('import android.graphics.drawable.Drawable;\n', 'import android.graphics.drawable.Drawable;\nimport android.media.AudioManager;\n')
s = s.replace('import android.os.SystemClock;\n', 'import android.os.SystemClock;\nimport android.provider.Settings;\n')

# No self-ADB health probe on startup anymore.
s = re.sub(
    r'\n\s*pool\.execute\(new Runnable\(\) \{\s*@Override public void run\(\) \{ adbManager\.checkAndRepair\(\); \}\s*\}\);',
    '', s, count=1
)

# Ensure native control whenever service starts.
if 'ensureNativeControl();' not in s:
    s = s.replace('        adbManager = new AdbManager(this);\n        running = true;',
                  '        adbManager = new AdbManager(this);\n        ensureNativeControl();\n        running = true;')

# Native app launch and best-effort stop.
s = s.replace(
    'if ("launch".equals(type)) return jsonResponse(resultJson("Launch", adb("monkey -p " + pkg + " 1")));',
    'if ("launch".equals(type)) return jsonResponse(resultJson("Launch", nativeLaunch(pkg)));'
)
s = s.replace(
    'if ("force-stop".equals(type)) return jsonResponse(resultJson("Force stop", adb("am force-stop " + pkg)));',
    'if ("force-stop".equals(type)) return jsonResponse(resultJson("Stop", nativeStop(pkg)));'
)

# Native remote path.
remote_pattern = re.compile(r'''        if \("/api/remote"\.equals\(path\)\) \{.*?        \}\n\n        if \("/api/update"\.equals\(path\)\)''', re.S)
remote_repl = '''        if ("/api/remote".equals(path)) {
            markActive();
            String key = param(query, "key");
            return jsonResponse(resultJson("Remote", nativeRemote(key)));
        }

        if ("/api/update".equals(path))'''
s, n = remote_pattern.subn(remote_repl, s, count=1)
if n != 1:
    raise SystemExit("v2.8 could not replace remote route")

# Native maintenance/sleep. Cache trim becomes a graceful optional feature.
s = s.replace(
    'if ("kill-background".equals(type)) return jsonResponse(resultJson("Clean background", adb("am kill-all")));',
    'if ("kill-background".equals(type)) return jsonResponse(resultJson("Clean background", nativeKillBackground()));'
)
s = s.replace(
    'if ("trim-cache".equals(type)) return jsonResponse(resultJson("Trim caches", adb("pm trim-caches 999999999999")));',
    'if ("trim-cache".equals(type)) return jsonResponse(resultJson("Trim caches", "Fire OS cache trim needs privileged ADB; skipped safely"));'
)
# Formatting variants from old source.
s = s.replace(
    'if ("trim-cache".equals(type)) return jsonResponse(resultJson("Trim caches", adb("pm trim-caches 999999999999"));',
    'if ("trim-cache".equals(type)) return jsonResponse(resultJson("Trim caches", "Fire OS cache trim needs privileged ADB; skipped safely"));'
)
s = s.replace('String r = adb("input keyevent 223");', 'String r = nativeSleep();')
s = s.replace('adb("input keyevent 223");\n        forceIdle();', 'nativeSleep();\n        forceIdle();')
s = s.replace('String wake = adb("input keyevent 224");', 'String wake = nativeWake();')

# Add native control state to status JSON, while leaving ADB state available only
# as diagnostic information.
if '\\"controlState\\"' not in s:
    needle = '",\\\"adbError\\\":\\\"" + json(adbManager == null ? "" : adbManager.getLastError()) + "\\\"" +\n                ",\\\"port\\\":" + PORT +'
    repl = '",\\\"adbError\\\":\\\"" + json(adbManager == null ? "" : adbManager.getLastError()) + "\\\"" +\n                ",\\\"controlState\\\":\\\"" + json(nativeControlState()) + "\\\"" +\n                ",\\\"port\\\":" + PORT +'
    if needle in s:
        s = s.replace(needle, repl, 1)
    else:
        needle2 = '",\\\"idleTimeoutMs\\\":" + IDLE_TIMEOUT_MS +\n                ",\\\"port\\\":" + PORT +'
        repl2 = '",\\\"idleTimeoutMs\\\":" + IDLE_TIMEOUT_MS +\n                ",\\\"controlState\\\":\\\"" + json(nativeControlState()) + "\\\"" +\n                ",\\\"port\\\":" + PORT +'
        if needle2 in s: s = s.replace(needle2, repl2, 1)

helpers = r'''    private boolean hasWriteSecureSettings() {
        return checkCallingOrSelfPermission("android.permission.WRITE_SECURE_SETTINGS") == PackageManager.PERMISSION_GRANTED;
    }

    private void ensureNativeControl() {
        if (!hasWriteSecureSettings()) return;
        try {
            ComponentName component = new ComponentName(this, FireAccessibilityService.class);
            String wanted = component.flattenToString();
            String enabled = Settings.Secure.getString(getContentResolver(), Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
            if (enabled == null) enabled = "";
            boolean present = false;
            for (String part : enabled.split(":")) {
                if (wanted.equals(part)) { present = true; break; }
            }
            if (!present) {
                String next = enabled.length() == 0 ? wanted : enabled + ":" + wanted;
                Settings.Secure.putString(getContentResolver(), Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES, next);
            }
            Settings.Secure.putInt(getContentResolver(), Settings.Secure.ACCESSIBILITY_ENABLED, 1);
        } catch (Throwable e) {
            Log.w(TAG, "Could not self-enable accessibility", e);
        }
    }

    private String nativeControlState() {
        if (!hasWriteSecureSettings()) return "bootstrap";
        if (FireAccessibilityService.getInstance() != null) return "ready";
        ensureNativeControl();
        return "enabling";
    }

    private String nativeLaunch(String pkg) {
        try {
            Intent intent = getPackageManager().getLaunchIntentForPackage(pkg);
            if (intent == null) return "App has no launch activity";
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
            startActivity(intent);
            return "Opened";
        } catch (Throwable e) {
            return "Launch failed: " + e.getMessage();
        }
    }

    private String nativeStop(String pkg) {
        try {
            ActivityManager am = (ActivityManager) getSystemService(ACTIVITY_SERVICE);
            if (am == null) return "Activity manager unavailable";
            am.killBackgroundProcesses(pkg);
            return "Background process stop requested";
        } catch (Throwable e) {
            return "Stop failed: " + e.getMessage();
        }
    }

    private String nativeKillBackground() {
        try {
            ActivityManager am = (ActivityManager) getSystemService(ACTIVITY_SERVICE);
            if (am == null) return "Activity manager unavailable";
            int count = 0;
            for (ApplicationInfo info : getPackageManager().getInstalledApplications(0)) {
                if (getPackageName().equals(info.packageName)) continue;
                if ((info.flags & ApplicationInfo.FLAG_SYSTEM) != 0) continue;
                try {
                    am.killBackgroundProcesses(info.packageName);
                    count++;
                } catch (Throwable ignored) {}
            }
            return "Background cleanup requested for " + count + " apps";
        } catch (Throwable e) {
            return "Cleanup failed: " + e.getMessage();
        }
    }

    private String nativeRemote(String key) {
        if ("volup".equals(key) || "voldown".equals(key) || "mute".equals(key)) {
            try {
                AudioManager audio = (AudioManager) getSystemService(AUDIO_SERVICE);
                if (audio == null) return "Audio manager unavailable";
                if ("volup".equals(key)) {
                    audio.adjustSuggestedStreamVolume(AudioManager.ADJUST_RAISE, AudioManager.STREAM_MUSIC, AudioManager.FLAG_SHOW_UI);
                    return "Volume +";
                }
                if ("voldown".equals(key)) {
                    audio.adjustSuggestedStreamVolume(AudioManager.ADJUST_LOWER, AudioManager.STREAM_MUSIC, AudioManager.FLAG_SHOW_UI);
                    return "Volume -";
                }
                if (Build.VERSION.SDK_INT >= 23) {
                    audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_TOGGLE_MUTE, AudioManager.FLAG_SHOW_UI);
                } else {
                    audio.setStreamMute(AudioManager.STREAM_MUSIC, !audio.isStreamMute(AudioManager.STREAM_MUSIC));
                }
                return "Mute";
            } catch (Throwable e) {
                return "Volume control failed: " + e.getMessage();
            }
        }

        ensureNativeControl();
        FireAccessibilityService service = FireAccessibilityService.getInstance();
        if (service == null) {
            try { Thread.sleep(180L); } catch (InterruptedException ignored) {}
            service = FireAccessibilityService.getInstance();
        }
        if (service == null) {
            return hasWriteSecureSettings()
                    ? "Accessibility is starting; try again in a moment"
                    : "One-time bootstrap required";
        }
        return service.command(key);
    }

    @SuppressWarnings("deprecation")
    private String nativeWake() {
        try {
            PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
            if (pm == null) return "Power manager unavailable";
            int flags = PowerManager.SCREEN_BRIGHT_WAKE_LOCK |
                    PowerManager.ACQUIRE_CAUSES_WAKEUP |
                    PowerManager.ON_AFTER_RELEASE;
            PowerManager.WakeLock lock = pm.newWakeLock(flags, "FireWebRemote:nativeWake");
            lock.acquire(2500L);
            return "Awake";
        } catch (Throwable e) {
            return "Wake failed: " + e.getMessage();
        }
    }

    private String nativeSleep() {
        try {
            DevicePolicyManager dpm = (DevicePolicyManager) getSystemService(DEVICE_POLICY_SERVICE);
            ComponentName admin = new ComponentName(this, FireDeviceAdminReceiver.class);
            if (dpm == null || !dpm.isAdminActive(admin)) {
                return "One-time Device Admin bootstrap required";
            }
            dpm.lockNow();
            return "Sleep";
        } catch (Throwable e) {
            return "Sleep failed: " + e.getMessage();
        }
    }

'''
marker = '    private String adb(String command) {\n'
if 'private String nativeRemote(String key)' not in s:
    if marker not in s: raise SystemExit("v2.8 adb() marker not found")
    s = s.replace(marker, helpers + marker, 1)

p.write_text(s, encoding="utf-8")

# ---- Web UI ---------------------------------------------------------------
p = Path("app/src/main/assets/index.html")
s = p.read_text(encoding="utf-8")

# Track native control state.
s = s.replace("adbError:''};", "adbError:'',controlState:'checking'};")
s = s.replace("S.adbError=d.adbError||'';", "S.adbError=d.adbError||'';S.controlState=d.controlState||'checking';")

# Top pill now represents the control path that actually drives the remote.
s = s.replace(
    "$('state').textContent=(S.adbState&&S.adbState!=='ready'&&S.adbState!=='checking')?('ADB · '+S.adbState):('Awake · '+Math.ceil(S.remain/1000)+'s');",
    "$('state').textContent=S.controlState==='ready'?('Ready · '+Math.ceil(S.remain/1000)+'s'):(S.controlState==='bootstrap'?'Setup · once':'Control · starting');"
)

p.write_text(s, encoding="utf-8")
