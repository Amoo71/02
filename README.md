# Fire Web Remote 2.0

Lightweight Fire TV background controller with a modern local web UI on **port 8765**.

## Included

- Auto-start after Fire TV reboot.
- Foreground service with no periodic polling.
- **Ultra Idle after 30 seconds without an operation.**
- In Ultra Idle the website only exposes **Wake** (plus read-only status).
- Wake re-enables operations for 30 seconds and sends `KEYCODE_WAKEUP`.
- English macOS-like dark web interface.
- Installed app list with search, sorting, system-app toggle and browser-persistent Hide/Unhide.
- Launch and Force Stop actions for installed apps.
- Quick launch for SmartTube (`org.smarttube.stable`) and VPN (`net.vypn.app`).
- Maintenance tools: `am kill-all`, cache trimming, Home, Back and Sleep.
- No arbitrary remote shell endpoint.

## Build

The complete Android source is stored directly in this repository. GitHub Actions builds the debug APK automatically from `main`.

## Install

Download the `FireWebRemote-2.0-APK` artifact from the latest successful GitHub Actions run, extract it, then:

```bash
adb connect FIRE-TV-IP:5555
adb install -r FireWebRemote-2.0-debug.apk
adb shell am start -n dev.fireweb.remote/.MainActivity
```

Open on the iPhone:

```text
http://FIRE-TV-IP:8765
```

ADB debugging must remain enabled. On the first remote action Fire TV may ask you to approve the embedded ADB RSA key once.

## Power behavior

The HTTP server blocks while waiting for connections and has no polling loop. No permanent wake lock is held. `/api/wake` uses only a short five-second partial wake lock. The listener itself must stay alive so the iPhone can wake the controller over the LAN.

## Security

Use this only on a trusted LAN. Do not expose port 8765 to the internet.
