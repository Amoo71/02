# Fire Web Remote 2.1

Lightweight Fire TV background controller with a local iPhone-first web UI on **port 8765**.

## 2.1

- Single-screen mobile layout with no page scrolling.
- Apps / Remote / Tools tabs.
- Nintendo/handheld-style paged app grid with real installed-app icons.
- Search, system-app filter, Hide/Unhide, Open and Force Stop.
- Remote D-pad: Up/Down/Left/Right/OK plus Home, Back, Menu, Mute and Volume +/-.
- SmartTube and VYPN quick launch.
- Background-process cleanup and cache trimming.
- 30-second Ultra Idle starts only after actual web use stops. Active visible use sends a lightweight keepalive.
- Wake-only UI while idle.
- Stable download name: `dist/FireWebRemote.apk`.
- Self-update API downloads the latest APK and restarts the controller.
- Package ID remains `dev.fireweb.remote`.

## Install

Open on the iPhone after installation:

```text
http://FIRE-TV-IP:8765
```

ADB debugging must remain enabled because Fire Web Remote uses the Fire TV's local ADB service for remote-control actions.

## Updates

The latest build is always published as:

```text
https://raw.githubusercontent.com/Amoo71/02/main/dist/FireWebRemote.apk
```

Because GitHub debug builds can receive different debug signing certificates between runners, the first transition from an older build can require one uninstall/reinstall. The 2.1 updater is designed to handle later replacement attempts itself and preserve the local ADB authorization data where Fire OS permits it.

## Security

The HTTP service is intended only for a trusted local network. Do not expose port 8765 to the internet. There is no arbitrary remote shell endpoint.
