package org.telegram.ui;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.text.InputType;
import android.util.TypedValue;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.derenguhgram.DerenguhBridgeManager;
import org.derenguhgram.privacy.PrivacyController;
import org.derenguhgram.proxy.DerenguhProto;
import org.telegram.messenger.AndroidUtilities;
import org.telegram.messenger.ApplicationLoader;
import org.telegram.messenger.FileLog;
import org.telegram.messenger.MessagesController;
import org.telegram.messenger.NotificationCenter;
import org.telegram.messenger.R;
import org.telegram.messenger.SharedConfig;
import org.telegram.messenger.Utilities;
import org.telegram.tgnet.ConnectionsManager;
import org.telegram.ui.ActionBar.ActionBar;
import org.telegram.ui.ActionBar.AlertDialog;
import org.telegram.ui.ActionBar.BaseFragment;
import org.telegram.ui.ActionBar.Theme;
import org.telegram.ui.ActionBar.ThemeBind;
import org.telegram.ui.Cells.HeaderCell;
import org.telegram.ui.Cells.TextCheckCell;
import org.telegram.ui.Cells.TextSettingsCell;
import org.telegram.ui.Components.EditTextBoldCursor;
import org.telegram.ui.Components.LayoutHelper;
import org.telegram.utils.proxy.ProxySettings;
import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;
import java.util.Locale;

/** Native themed Telegram screen: Derenguh proxy, privacy modes, ClanSecrets tools. */
public class DerenguhGramFragment extends BaseFragment {
    private LinearLayout content;
    private EditTextBoldCursor host, port, sni, key;
    private TextCheckCell invisible, noRead, noTyping;
    private TextView status;
    private static final int REQ_LOG = 4201, REQ_MEDIA = 4202;

    @Override public View createView(Context context) {
        actionBar.setBackButtonImage(R.drawable.ic_ab_back);
        actionBar.setTitle("DerenguhGram");
        actionBar.setActionBarMenuOnItemClick(new ActionBar.ActionBarMenuOnItemClick() {
            @Override public void onItemClick(int id) { if (id == -1) finishFragment(); }
        });
        FrameLayout root = new FrameLayout(context);
        ThemeBind.backgroundColor(root, Theme.key_windowBackgroundWhite);
        ScrollView scroll = new ScrollView(context);
        root.addView(scroll, LayoutHelper.createFrame(LayoutHelper.MATCH_PARENT, LayoutHelper.MATCH_PARENT));
        content = new LinearLayout(context); content.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(content, new ScrollView.LayoutParams(-1, -2));
        addHeader("DerenguhGram Proxy");
        host = field("Сервер", ""); port = field("Порт", "3183"); sni = field("SNI (маскировка)", "music.yandex.ru"); key = field("Ключ (base64url, 16 байт)", "");
        key.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        SharedPreferences p = MessagesController.getGlobalMainSettings();
        ProxySettings old = ProxySettings.fromSharedPreferences(p);
        if (old.getType() == ProxySettings.Type.DERENGUH) { host.setText(old.getAddress()); port.setText(String.valueOf(old.getPort())); sni.setText(old.getUser()); key.setText(old.getSecret()); }
        TextSettingsCell connect = new TextSettingsCell(context); connect.setText("Подключить / сохранить", false);
        connect.setOnClickListener(v -> connect()); content.addView(connect, LayoutHelper.createLinear(-1, 50));
        TextSettingsCell disable = new TextSettingsCell(context); disable.setText("Отключить прокси", false);
        disable.setOnClickListener(v -> { SharedPreferences.Editor e=p.edit(); e.putBoolean("proxy_enabled", false); e.putInt("proxy_type", 0); e.apply(); SharedConfig.currentProxy=null; ConnectionsManager.setProxySettings(false, null); DerenguhBridgeManager.stop(); NotificationCenter.getGlobalInstance().postNotificationName(NotificationCenter.proxySettingsChanged); status.setText("Прокси отключён"); });
        content.addView(disable, LayoutHelper.createLinear(-1, 50));
        status = label("Статус: не подключено"); content.addView(status, LayoutHelper.createLinear(-1, -2, 16, 4, 16, 8));
        addHeader("Приватность");
        PrivacyController.INSTANCE.init(context);
        invisible = check("Невидимка (не показывать онлайн)", PrivacyController.INSTANCE.getInvisible()); invisible.setOnClickListener(v -> { boolean x=!invisible.isChecked(); invisible.setChecked(x); PrivacyController.INSTANCE.setInvisible(context, x); });
        noRead = check("Нечиталка (не отправлять прочтение)", PrivacyController.INSTANCE.getNoReadReceipts()); noRead.setOnClickListener(v -> { boolean x=!noRead.isChecked(); noRead.setChecked(x); PrivacyController.INSTANCE.setNoReadReceipts(context, x); });
        noTyping = check("Неписалка (не отправлять «печатает…»)", PrivacyController.INSTANCE.getNoTyping()); noTyping.setOnClickListener(v -> { boolean x=!noTyping.isChecked(); noTyping.setChecked(x); PrivacyController.INSTANCE.setNoTyping(context, x); });
        content.addView(invisible, LayoutHelper.createLinear(-1, 50)); content.addView(noRead, LayoutHelper.createLinear(-1, 50)); content.addView(noTyping, LayoutHelper.createLinear(-1, 50));
        addHeader("ClanSecrets");
        row("Журнал клиента", v -> showLogs());
        row("Путь к кэшу", v -> new AlertDialog.Builder(getParentActivity()).setTitle("Кэш").setMessage(ApplicationLoader.applicationContext.getCacheDir().getAbsolutePath()).setPositiveButton("OK", null).show());
        row("Открыть файлы приложения", v -> openCache());
        row("Экспорт журнала", v -> { Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT); i.addCategory(Intent.CATEGORY_OPENABLE); i.setType("text/plain"); i.putExtra(Intent.EXTRA_TITLE, "derenguh-log.txt"); startActivityForResult(i, REQ_LOG); });
        row("Экспорт обычных медиа из кэша", v -> { Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE); startActivityForResult(i, REQ_MEDIA); });
        content.addView(label("Защищённые и самоуничтожающиеся медиа не перехватываются: уважайте выбор отправителя. Кэш Telegram зашифрован; экспорт работает с уже расшифрованными обычными файлами приложения."), LayoutHelper.createLinear(-1, -2, 16, 8, 16, 24));
        fragmentView = root; return root;
    }
    private void addHeader(String t){ HeaderCell h=new HeaderCell(getParentActivity()); h.setText(t); content.addView(h, LayoutHelper.createLinear(-1,-2)); }
    private TextView label(String t){ TextView v=new TextView(getParentActivity()); v.setText(t); v.setTextSize(TypedValue.COMPLEX_UNIT_DIP,13); ThemeBind.textColor(v, Theme.key_windowBackgroundWhiteGrayText); return v; }
    private EditTextBoldCursor field(String hint,String val){ EditTextBoldCursor e=new EditTextBoldCursor(getParentActivity()); e.setTextSize(TypedValue.COMPLEX_UNIT_DIP,16); e.setHint(hint); e.setHintText(hint); e.setHintColor(Theme.getColor(Theme.key_windowBackgroundWhiteHintText)); e.setCursorColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText)); e.setText(val); e.setSingleLine(true); e.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS); ThemeBind.textColor(e,Theme.key_windowBackgroundWhiteBlackText); e.setBackgroundDrawable(Theme.createSimpleSelectorRoundRectDrawable(AndroidUtilities.dp(8), Theme.getColor(Theme.key_windowBackgroundGray), Theme.getColor(Theme.key_listSelector))); e.setPadding(AndroidUtilities.dp(12),0,AndroidUtilities.dp(12),0); content.addView(e, LayoutHelper.createLinear(-1,48,16,6,16,6)); return e; }
    private TextCheckCell check(String t,boolean c){ TextCheckCell v=new TextCheckCell(getParentActivity()); v.setTextAndCheck(t,c,false); return v; }
    private void row(String t, View.OnClickListener l){ TextSettingsCell v=new TextSettingsCell(getParentActivity()); v.setText(t,false); v.setOnClickListener(l); content.addView(v, LayoutHelper.createLinear(-1,50)); }
    private void connect(){
        try {
            int po=Integer.parseInt(port.getText().toString().trim());
            String h=host.getText().toString().trim(), s=sni.getText().toString().trim().toLowerCase(Locale.ROOT), k=key.getText().toString().trim();
            boolean sniOk=false; for(kotlin.Pair<String,String> c: DerenguhProto.INSTANCE.getSNI_CHOICES()) if(c.getFirst().equals(s)) sniOk=true;
            if(h.isEmpty()||po<1||po>65535||!sniOk||k.length()<22){ status.setText("Проверьте сервер, порт, SNI и ключ"); return; }
            ProxySettings ps=new ProxySettings(ProxySettings.Type.DERENGUH,h,po,s,"",k);
            if(!ps.isValid()){ status.setText("Неверный ключ Derenguh (нужно 16 байт)"); return; }
            SharedPreferences.Editor e=MessagesController.getGlobalMainSettings().edit(); e.putBoolean("proxy_enabled",true); ps.toSharedPreferences(e); e.commit();
            SharedConfig.currentProxy=SharedConfig.addProxy(new SharedConfig.ProxyInfo(ps));
            ConnectionsManager.setProxySettings(true,ps);
            NotificationCenter.getGlobalInstance().postNotificationName(NotificationCenter.proxySettingsChanged);
            status.setText("Сохранено. Локальный мост: "+(DerenguhBridgeManager.isRunning()?"запущен":"ошибка"));
        } catch(Exception ex){ status.setText("Ошибка: "+ex.getMessage()); }
    }
    private void showLogs(){ String log=FileLog.getNetworkLogPath(); new AlertDialog.Builder(getParentActivity()).setTitle("Журнал").setMessage(log!=null&&!log.isEmpty()?log:"Сетевой журнал не включён в release-сборке").setPositiveButton("OK",null).show(); }
    private void openCache(){ File dir=getParentActivity().getExternalFilesDir(null); if(dir==null)dir=getParentActivity().getFilesDir(); File[] fs=dir.listFiles(); if(fs==null||fs.length==0){ android.widget.Toast.makeText(getParentActivity(), "Кэш пуст", android.widget.Toast.LENGTH_SHORT).show(); return;} CharSequence[] names=new CharSequence[fs.length]; for(int i=0;i<fs.length;i++)names[i]=fs[i].getName(); final File[] files=fs; new AlertDialog.Builder(getParentActivity()).setTitle("Файлы приложения").setItems(names,(d,w)->AndroidUtilities.openForView(files[w],files[w].getName(),null,getParentActivity(),getResourceProvider(),true)).show(); }
    @Override public void onActivityResultFragment(int requestCode,int resultCode,Intent data){
        if(resultCode!=Activity.RESULT_OK||data==null||data.getData()==null)return; Uri uri=data.getData();
        if(requestCode==REQ_LOG){ try(OutputStream os=getParentActivity().getContentResolver().openOutputStream(uri)){ String path=FileLog.getNetworkLogPath(); if(path!=null&&!path.isEmpty()&&new File(path).exists()){ try(FileInputStream in=new FileInputStream(path)){ byte[] b=new byte[8192]; int n; while((n=in.read(b))>0)os.write(b,0,n);} } else { os.write("DerenguhGram: сетевой журнал не включён\n".getBytes()); } android.widget.Toast.makeText(getParentActivity(), "Журнал сохранён", android.widget.Toast.LENGTH_SHORT).show(); }catch(Exception e){FileLog.e(e);} }
        else if(requestCode==REQ_MEDIA){ Utilities.globalQueue.postRunnable(()->{ int n=exportMedia(uri); AndroidUtilities.runOnUIThread(()->android.widget.Toast.makeText(getParentActivity(), "Экспортировано файлов: "+n, android.widget.Toast.LENGTH_SHORT).show()); }); }
    }
    private int exportMedia(Uri treeUri){
        int n=0; File dir=getParentActivity().getExternalFilesDir(null); if(dir==null)return 0; File[] fs=dir.listFiles(); if(fs==null)return 0;
        android.content.ContentResolver cr=getParentActivity().getContentResolver();
        String treeId=android.provider.DocumentsContract.getTreeDocumentId(treeUri);
        for(File f:fs){ if(!f.isFile())continue; String name=f.getName().toLowerCase(Locale.ROOT); if(!(name.endsWith(".jpg")||name.endsWith(".mp4")||name.endsWith(".mp3")||name.endsWith(".webm")||name.endsWith(".ogg")))continue;
            try{ Uri doc=android.provider.DocumentsContract.createDocument(cr, android.provider.DocumentsContract.buildDocumentUriUsingTree(treeUri,treeId), "application/octet-stream", f.getName()); if(doc==null)continue; try(OutputStream os=cr.openOutputStream(doc); FileInputStream in=new FileInputStream(f)){ byte[] b=new byte[16384]; int r; while((r=in.read(b))>0)os.write(b,0,r);} n++; }catch(Exception e){FileLog.e(e);} }
        return n;
    }
}
