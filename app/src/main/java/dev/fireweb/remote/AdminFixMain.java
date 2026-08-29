package dev.fireweb.remote;

import android.app.admin.DevicePolicyManager;
import android.content.ComponentName;
import android.content.Context;
import android.os.Process;

import java.lang.reflect.Method;

/**
 * Emergency helper for Fire OS builds that hide the Device Admin removal UI.
 *
 * This class is intentionally not exported as an Android component. It is only
 * meant to be launched with app_process under this application's own UID via
 * `run-as dev.fireweb.remote`. DevicePolicyManager permits the owner app to
 * remove its own active admin.
 */
public final class AdminFixMain {
    private AdminFixMain() {}

    public static void main(String[] args) {
        try {
            Context context = systemContext();
            DevicePolicyManager dpm = (DevicePolicyManager)
                    context.getSystemService(Context.DEVICE_POLICY_SERVICE);
            if (dpm == null) {
                System.err.println("ADMIN_FIX_ERROR: DevicePolicyManager unavailable");
                System.exit(2);
                return;
            }

            ComponentName admin = new ComponentName(
                    "dev.fireweb.remote",
                    "dev.fireweb.remote.FireDeviceAdminReceiver");

            System.out.println("ADMIN_FIX_UID=" + Process.myUid());
            if (!dpm.isAdminActive(admin)) {
                System.out.println("ADMIN_FIX_OK: already inactive");
                return;
            }

            dpm.removeActiveAdmin(admin);

            // removeActiveAdmin is asynchronous. Wait briefly so the shell can
            // immediately run `pm uninstall` after this helper exits.
            for (int i = 0; i < 24; i++) {
                if (!dpm.isAdminActive(admin)) {
                    System.out.println("ADMIN_FIX_OK: admin removed");
                    return;
                }
                try { Thread.sleep(250L); } catch (InterruptedException ignored) {}
            }

            System.err.println("ADMIN_FIX_PENDING: removal requested; wait 2 seconds and retry uninstall");
        } catch (Throwable t) {
            System.err.println("ADMIN_FIX_ERROR: " + t);
            t.printStackTrace(System.err);
            System.exit(1);
        }
    }

    private static Context systemContext() throws Exception {
        Class<?> activityThread = Class.forName("android.app.ActivityThread");
        Method systemMain = activityThread.getDeclaredMethod("systemMain");
        systemMain.setAccessible(true);
        Object thread = systemMain.invoke(null);
        Method getSystemContext = activityThread.getDeclaredMethod("getSystemContext");
        getSystemContext.setAccessible(true);
        return (Context) getSystemContext.invoke(thread);
    }
}
