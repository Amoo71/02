from pathlib import Path

# Preserve all important Fire Control state if the self-updater has to fall back
# to uninstall/install because Android rejects an in-place APK signature.
p = Path("app/src/main/java/dev/fireweb/remote/FireWebService.java")
s = p.read_text(encoding="utf-8")

backup = '            adb("run-as dev.fireweb.remote cat shared_prefs/adb_keys.xml > /data/local/tmp/fireweb-adb-keys.xml 2>/dev/null; true");\n'
backup_more = backup + \
    '            adb("run-as dev.fireweb.remote cat shared_prefs/fireweb_state.xml > /data/local/tmp/fireweb-state.xml 2>/dev/null; true");\n' + \
    '            adb("run-as dev.fireweb.remote cat shared_prefs/adb_manager.xml > /data/local/tmp/fireweb-adb-manager.xml 2>/dev/null; true");\n'
if backup in s and 'fireweb-state.xml' not in s:
    s = s.replace(backup, backup_more, 1)

restore = '''                    "  if [ -s /data/local/tmp/fireweb-adb-keys.xml ]; then " +
                    "    cat /data/local/tmp/fireweb-adb-keys.xml | run-as dev.fireweb.remote sh -c 'cat > shared_prefs/adb_keys.xml'; " +
                    "  fi; " +
'''
restore_more = restore + '''                    "  if [ -s /data/local/tmp/fireweb-state.xml ]; then " +
                    "    cat /data/local/tmp/fireweb-state.xml | run-as dev.fireweb.remote sh -c 'cat > shared_prefs/fireweb_state.xml'; " +
                    "  fi; " +
                    "  if [ -s /data/local/tmp/fireweb-adb-manager.xml ]; then " +
                    "    cat /data/local/tmp/fireweb-adb-manager.xml | run-as dev.fireweb.remote sh -c 'cat > shared_prefs/adb_manager.xml'; " +
                    "  fi; " +
'''
if restore in s and "shared_prefs/fireweb_state.xml';" not in s:
    s = s.replace(restore, restore_more, 1)

p.write_text(s, encoding="utf-8")

# Clean temporary backup files only after the new service has started and ADB is
# healthy, so a failed update does not destroy the recovery copy prematurely.
p = Path("app/src/main/java/dev/fireweb/remote/AdbManager.java")
s = p.read_text(encoding="utf-8")
s = s.replace(
    '"/data/local/tmp/fireweb-update.log.old 2>/dev/null; true", 7000);',
    '"/data/local/tmp/fireweb-update.log.old " +\n'
    '                    ' '"/data/local/tmp/fireweb-adb-keys.xml " +\n'
    '                    ' '"/data/local/tmp/fireweb-state.xml " +\n'
    '                    ' '"/data/local/tmp/fireweb-adb-manager.xml 2>/dev/null; true", 7000);'
)
p.write_text(s, encoding="utf-8")
