#!/usr/bin/env python3
"""Apply DerenguhGram overlay + minimal audited patches to pinned DrKLO/Telegram."""
from pathlib import Path
import argparse, subprocess, sys, shutil

ROOT=Path(__file__).resolve().parents[1]

def patch(path, old, new, count=1):
    p=Path(path); s=p.read_text()
    if s.count(old)!=count: raise SystemExit(f'anchor mismatch in {p} ({s.count(old)}!={count}): {old[:120]!r}')
    p.write_text(s.replace(old,new))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('target',type=Path); a=ap.parse_args(); t=a.target
    subprocess.run([sys.executable,str(ROOT/'scripts/apply_overlay.py'),str(ROOT/'integrations/android'),str(t/'TMessagesProj/src/main/java')],check=True)
    j=t/'TMessagesProj/src/main/java'
    p=j/'org/telegram/utils/proxy/ProxySettings.java'
    patch(p,'        WEB\n    }','        WEB,\n        DERENGUH\n    }')
    patch(p,'''        } else if (type == Type.SOCKS5) {
            secret = "";
            port = builder.port;
            user = builder.user;
            password = builder.password;
        } else {''','''        } else if (type == Type.SOCKS5) {
            secret = "";
            port = builder.port;
            user = builder.user;
            password = builder.password;
        } else if (type == Type.DERENGUH) {
            secret = builder.secret;
            port = builder.port;
            user = builder.user; // SNI
            password = "";
        } else {''')
    patch(p,'''        return type == Type.WEB
                ? isValidWebAddress(address) && isValidWebProxySecret(secret)
                : port > 0;''','''        if (type == Type.WEB) return isValidWebAddress(address) && isValidWebProxySecret(secret);
        if (type == Type.DERENGUH) {
            if (port <= 0 || port > 65535 || user.isEmpty()) return false;
            try { return Base64.decode(secret, Base64.URL_SAFE | Base64.NO_PADDING | Base64.NO_WRAP).length == 16; }
            catch (Exception e) { return false; }
        }
        return port > 0;''')
    patch(p,'''            case WEB:
                url = new StringBuilder("https://t.me/webproxy?");
                break;''','''            case WEB:
                url = new StringBuilder("https://t.me/webproxy?");
                break;
            case DERENGUH:
                try {
                    return "derenguh://proxy?server=" + URLEncoder.encode(address, "UTF-8") + "&port=" + port
                        + "&sni=" + URLEncoder.encode(user, "UTF-8") + "&key=" + URLEncoder.encode(secret, "UTF-8");
                } catch (UnsupportedEncodingException e) { return ""; }''')
    patch(p,'''            case WEB:
                editor.putString("proxy_secret", secret);
                editor.remove("proxy_port");
                editor.remove("proxy_pass");
                editor.remove("proxy_user");
                break;''','''            case WEB:
                editor.putString("proxy_secret", secret);
                editor.remove("proxy_port");
                editor.remove("proxy_pass");
                editor.remove("proxy_user");
                break;
            case DERENGUH:
                editor.putString("proxy_secret", secret);
                editor.putInt("proxy_port", port);
                editor.putString("proxy_user", user);
                editor.remove("proxy_pass");
                break;''')
    patch(p,'''            } else if (scheme.equalsIgnoreCase("tg")) {''','''            } else if (scheme.equalsIgnoreCase("derenguh")) {
                return builder().setType(Type.DERENGUH)
                    .setAddress(uri.getQueryParameter("server"))
                    .setPort(Integer.parseInt(uri.getQueryParameter("port") == null ? "3183" : uri.getQueryParameter("port")))
                    .setUser(uri.getQueryParameter("sni"))
                    .setSecret(uri.getQueryParameter("key")).build();
            } else if (scheme.equalsIgnoreCase("tg")) {''')
    patch(p,'''            case WEB:
                return 2;''','''            case WEB:
                return 2;
            case DERENGUH:
                return 3;''')
    patch(p,'''            case 2:
                return Type.WEB;''','''            case 2:
                return Type.WEB;
            case 3:
                return Type.DERENGUH;''')
    # ConnectionsManager: init, static setter, checker
    p=j/'org/telegram/tgnet/ConnectionsManager.java'
    patch(p,'''            if (proxySettings.getType() == ProxySettings.Type.WEB) {
                int localPort = WebProxyTransport.start(proxySettings.getAddress(), proxySettings.getSecret());
                native_setProxySettings(currentAccount, "127.0.0.1", localPort != 0 ? localPort : 9, "", "",
                        proxySettings.getSecret());
            } else {''','''            if (proxySettings.getType() == ProxySettings.Type.WEB) {
                int localPort = WebProxyTransport.start(proxySettings.getAddress(), proxySettings.getSecret());
                native_setProxySettings(currentAccount, "127.0.0.1", localPort != 0 ? localPort : 9, "", "",
                        proxySettings.getSecret());
            } else if (proxySettings.getType() == ProxySettings.Type.DERENGUH) {
                int localPort = org.derenguhgram.DerenguhBridgeManager.start(proxySettings);
                native_setProxySettings(currentAccount, "127.0.0.1", localPort, "", "", "");
            } else {
                org.derenguhgram.DerenguhBridgeManager.stop();''')
    patch(p,'''        if (settings.getType() == ProxySettings.Type.WEB) {
            WebProxyConnectionTester.getInstance().checkProxy(settings, requestTimeDelegate, this::checkWebProxyInternal);
            return 0;
        }''','''        if (settings.getType() == ProxySettings.Type.WEB) {
            WebProxyConnectionTester.getInstance().checkProxy(settings, requestTimeDelegate, this::checkWebProxyInternal);
            return 0;
        }
        if (settings.getType() == ProxySettings.Type.DERENGUH) {
            int localPort = org.derenguhgram.DerenguhBridgeManager.start(settings);
            return native_checkProxy(currentAccount, "127.0.0.1", localPort, "", "", "", requestTimeDelegate);
        }''')
    patch(p,'''            if (settings.getType() == ProxySettings.Type.WEB) {
                int localPort = WebProxyTransport.start(address, secret);
                address = "127.0.0.1";
                port = localPort != 0 ? localPort : 9;
                username = "";
                password = "";
            } else {
                WebProxyTransport.stop();
            }
        } else {
            WebProxyTransport.stop();
        }''','''            if (settings.getType() == ProxySettings.Type.WEB) {
                int localPort = WebProxyTransport.start(address, secret);
                address = "127.0.0.1";
                port = localPort != 0 ? localPort : 9;
                username = "";
                password = "";
                secret = settings.getSecret();
                org.derenguhgram.DerenguhBridgeManager.stop();
            } else if (settings.getType() == ProxySettings.Type.DERENGUH) {
                int localPort = org.derenguhgram.DerenguhBridgeManager.start(settings);
                address = "127.0.0.1"; port = localPort; username = ""; password = ""; secret = "";
                WebProxyTransport.stop();
            } else {
                WebProxyTransport.stop();
                org.derenguhgram.DerenguhBridgeManager.stop();
            }
        } else {
            WebProxyTransport.stop();
            org.derenguhgram.DerenguhBridgeManager.stop();
        }''')
    # Init privacy + restore bridge
    patch(j/'org/telegram/messenger/ApplicationLoader.java','''        SharedConfig.loadConfig();''','''        SharedConfig.loadConfig();
        org.derenguhgram.privacy.PrivacyController.INSTANCE.init(applicationContext);
        org.derenguhgram.DerenguhBridgeManager.applyFromPreferences();''')
    # Settings entry
    p=j/'org/telegram/ui/SettingsActivity.java'
    patch(p,'''        items.add(SettingCell.Factory.of(1, IconBackgroundColors.BLUE.top''','''        items.add(SettingCell.Factory.of(42, 0xFF7C4DFF, 0xFF448AFF, R.drawable.settings_privacy, "DerenguhGram", "Прокси · Приватность · ClanSecrets"));
        items.add(SettingCell.Factory.of(1, IconBackgroundColors.BLUE.top''')
    patch(p,'''        switch (item.id) {
            case 1:''','''        switch (item.id) {
            case 42:
                presentFragment(new DerenguhGramFragment());
                break;
            case 1:''')
    # Privacy gates
    p=j/'org/telegram/messenger/MessagesController.java'
    patch(p,'''    private void completeReadTask(ReadTask task) {''','''    private void completeReadTask(ReadTask task) {
        if (org.derenguhgram.privacy.PrivacyController.INSTANCE.getNoReadReceipts()) return;''')
    patch(p,'''    public void markMentionsAsRead(long dialogId, long topicId) {''','''    public void markMentionsAsRead(long dialogId, long topicId) {
        if (org.derenguhgram.privacy.PrivacyController.INSTANCE.getNoReadReceipts()) return;''')
    s=p.read_text(); idx=s.index('public boolean sendTyping(long dialogId, long threadMsgId, int action, String emojicon, int classGuid)'); brace=s.index('{',idx)
    s=s[:brace+1]+'\n        if (org.derenguhgram.privacy.PrivacyController.INSTANCE.getNoTyping()) return false;'+s[brace+1:]
    s=s.replace('''                        req.offline = false;''','''                        req.offline = org.derenguhgram.privacy.PrivacyController.INSTANCE.getInvisible();''')
    p.write_text(s)
    # Kotlin + tests + fork safety
    p=t/'TMessagesProj/build.gradle'
    patch(p,"apply plugin: 'com.android.library'","apply plugin: 'com.android.library'\napply plugin: 'org.jetbrains.kotlin.android'")
    patch(p,'''    lintOptions {''','''    testOptions {
        unitTests.returnDefaultValues = true
    }

    lintOptions {''')
    patch(p,'''dependencies {''','''dependencies {
    testImplementation 'junit:junit:4.13.2'
    testImplementation 'org.json:json:20240303'
    testImplementation 'org.jetbrains.kotlin:kotlin-test:2.1.0' ''')
    patch(j/'org/telegram/messenger/BuildVars.java','public static boolean SUPPORTS_PASSKEYS = true;','public static boolean SUPPORTS_PASSKEYS = false; // fork: do not become device passkey provider')
    tr=t/'TMessagesProj/src/test/java/org/derenguhgram'; tr.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'DerenguhGram-Client/android/src/test/java/org/derenguhgram/DerenguhInteropTest.kt',tr/'DerenguhInteropTest.kt')
    res=t/'TMessagesProj/src/test/resources'; res.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'DerenguhGram-Client/shared/test_vectors.json',res/'test_vectors.json')
    tp=tr/'DerenguhInteropTest.kt'; s=tp.read_text().replace('val text = File("../shared/test_vectors.json").readText()','val text = javaClass.getResourceAsStream("/test_vectors.json")!!.bufferedReader().use { it.readText() }'); tp.write_text(s)
    # Fragment uses builder API
    fp=j/'org/telegram/ui/DerenguhGramFragment.java'; s=fp.read_text().replace('ProxySettings ps=new ProxySettings(ProxySettings.Type.DERENGUH,h,po,s,"",k);','ProxySettings ps=ProxySettings.builder().setType(ProxySettings.Type.DERENGUH).setAddress(h).setPort(po).setUser(s).setSecret(k).build();'); fp.write_text(s)
    # App module: personal applicationId, readable release (no R8 stripping of reflection-heavy Telegram), demo signing already upstream.
    app=t/'TMessagesProj_App/build.gradle'
    patch(app,'defaultConfig.applicationId = APP_PACKAGE','defaultConfig.applicationId = "org.derenguhgram.personal"')
    patch(app,'''        release {
            debuggable false
            jniDebuggable false
            signingConfig signingConfigs.release
            minifyEnabled true
            shrinkResources true''','''        release {
            debuggable false
            jniDebuggable false
            signingConfig signingConfigs.release
            minifyEnabled false
            shrinkResources false''')
    gp=t/'gradle.properties'
    patch(gp,'APP_PACKAGE=org.telegram.messenger','APP_PACKAGE=org.derenguhgram.personal')
    patch(gp,'org.gradle.jvmargs=-Xmx8g -XX:MaxMetaspaceSize=1g','org.gradle.jvmargs=-Xmx6g -XX:MaxMetaspaceSize=1g')
    print('Android integration applied')
if __name__=='__main__': main()
