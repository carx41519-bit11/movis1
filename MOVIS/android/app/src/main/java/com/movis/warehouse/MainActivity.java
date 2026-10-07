package com.movis.warehouse;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.content.res.ColorStateList;
import android.view.Gravity;
import android.view.WindowManager;
import android.os.Build;
import android.net.Uri;
import android.os.Bundle;
import android.provider.MediaStore;
import android.text.InputType;
import android.util.Base64;
import android.view.View;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;

/** Native Android capstone client. The server remains authoritative for stock and permissions. */
public class MainActivity extends Activity {
    private static final String CLOUD_SERVER="https://movis-1fxf.onrender.com";
    private static final int INK=Color.rgb(23,43,57), TEAL=Color.rgb(8,127,114), MUTED=Color.rgb(98,115,128), PAPER=Color.rgb(243,246,248), LINE=Color.rgb(220,228,231);
    private LinearLayout root, body, navigation, statusBox;
    private ProgressBar progress;
    private TextView dialogError;
    private final ArrayList<Button> actions=new ArrayList<>();
    private TextView message;
    private String base=CLOUD_SERVER, token="", role="", username="", current="Inventory";
    private JSONObject inventory=new JSONObject(), scan;
    private Bitmap photo;
    private int photoLocation=-1;
    private int scanPurpose=0;
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final HashMap<String,String> pendingKeys=new HashMap<>();
    private boolean busy=false;
    interface Reply { void done(JSONObject value) throws Exception; }
    interface Work { JSONObject run() throws Exception; }
    private static class ApiFailure extends IOException {
        final int status;
        ApiFailure(int status,String message){super(message);this.status=status;}
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        // This cloud edition replaces saved local addresses from earlier installations.
        base=CLOUD_SERVER;
        getPreferences(MODE_PRIVATE).edit().putString("server",base).apply();
        if(state!=null) { photoLocation=state.getInt("photoLocation",-1); }
        loginScreen();
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state); state.putInt("photoLocation",photoLocation);
    }
    @Override protected void onDestroy() { super.onDestroy(); worker.shutdownNow(); }
    private int dp(int n) { return (int)(getResources().getDisplayMetrics().density*n); }
    private LinearLayout column() { LinearLayout v=new LinearLayout(this); v.setOrientation(LinearLayout.VERTICAL); return v; }
    private GradientDrawable surface(int color,int radius,int border) { GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));if(border!=0)d.setStroke(dp(1),border);return d; }
    private TextView text(String s,int size) {
        TextView v=new TextView(this);v.setText(s);v.setTextSize(size);v.setTextColor(INK);v.setFontFeatureSettings("tnum");v.setPadding(0,dp(4),0,dp(4));v.setLineSpacing(dp(2),1);return v;
    }
    private TextView heading(String s,int size) { TextView v=text(s,size);v.setTypeface(Typeface.DEFAULT,Typeface.BOLD);return v; }
    private void title(String s) { TextView v=heading(s,26);v.setPadding(0,dp(12),0,dp(12));body.addView(v); }
    private void note(String s) { TextView v=text(s,14);v.setTextColor(MUTED);v.setPadding(0,dp(4),0,dp(12));body.addView(v); }
    private LinearLayout card(LinearLayout parent) { LinearLayout v=column();v.setPadding(dp(16),dp(14),dp(16),dp(14));v.setBackground(surface(Color.WHITE,14,LINE));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.bottomMargin=dp(14);parent.addView(v,lp);return v; }
    private void section(String name) { TextView v=heading(name,18);v.setPadding(0,dp(14),0,dp(8));body.addView(v); }
    private void banner(String s) { TextView v=text(s,14);v.setTextColor(Color.rgb(120,84,21));v.setPadding(dp(14),dp(12),dp(14),dp(12));v.setBackground(surface(Color.rgb(255,247,228),12,Color.rgb(235,218,179)));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.bottomMargin=dp(12);body.addView(v,lp); }
    private void shell(String subtitle) {
        actions.clear();root=column();root.setBackgroundColor(PAPER);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        getWindow().setStatusBarColor(PAPER);getWindow().setNavigationBarColor(Color.WHITE);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR|View.SYSTEM_UI_FLAG_LAYOUT_STABLE|View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN|View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        root.setOnApplyWindowInsetsListener((view,insets)->{if(Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(android.view.WindowInsets.Type.systemBars()|android.view.WindowInsets.Type.displayCutout());android.graphics.Insets ime=insets.getInsets(android.view.WindowInsets.Type.ime());view.setPadding(bars.left,bars.top,bars.right,Math.max(bars.bottom,ime.bottom));}else view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;});
        LinearLayout top=new LinearLayout(this);top.setGravity(Gravity.CENTER_VERTICAL);top.setPadding(dp(20),dp(14),dp(16),dp(14));
        TextView mark=heading("M",22);mark.setGravity(Gravity.CENTER);mark.setTextColor(Color.WHITE);mark.setBackground(surface(TEAL,12,0));top.addView(mark,new LinearLayout.LayoutParams(dp(42),dp(42)));
        LinearLayout brand=column();LinearLayout.LayoutParams brandLp=new LinearLayout.LayoutParams(0,-2,1);brandLp.leftMargin=dp(12);top.addView(brand,brandLp);brand.addView(heading("MOVIS",20));TextView sub=text(subtitle,12);sub.setTextColor(MUTED);brand.addView(sub);
        if(!token.isEmpty()){TextView menu=text("•••",22);menu.setGravity(Gravity.CENTER);menu.setContentDescription("Account and warehouse actions");top.addView(menu,new LinearLayout.LayoutParams(dp(48),dp(48)));menu.setOnClickListener(v->{if(busy)return;PopupMenu popup=new PopupMenu(this,menu);popup.getMenu().add("Refresh inventory");if(role.equals("admin"))popup.getMenu().add("Manage warehouse");popup.getMenu().add("Sign out");popup.setOnMenuItemClickListener(item->{String name=item.getTitle().toString();if(name.equals("Refresh inventory"))loadInventory();else if(name.equals("Manage warehouse"))home("Manage");else task(()->api("/logout",obj()),r->{token="";scan=null;photo=null;photoLocation=-1;pendingKeys.clear();loginScreen();});return true;});popup.show();});}
        root.addView(top);
        statusBox=new LinearLayout(this);statusBox.setGravity(Gravity.CENTER_VERTICAL);statusBox.setPadding(dp(16),dp(8),dp(16),dp(8));statusBox.setVisibility(View.GONE);progress=new ProgressBar(this);statusBox.addView(progress,new LinearLayout.LayoutParams(dp(22),dp(22)));message=text("",14);LinearLayout.LayoutParams mlp=new LinearLayout.LayoutParams(0,-2,1);mlp.leftMargin=dp(10);statusBox.addView(message,mlp);root.addView(statusBox);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setClipToPadding(false);body=column();body.setPadding(dp(20),0,dp(20),dp(24));scroll.addView(body);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        navigation=column();root.addView(navigation);setContentView(root);root.requestApplyInsets();
    }
    private EditText field(LinearLayout parent,String hint, boolean number) {
        TextView label=text(hint,14);label.setTypeface(Typeface.DEFAULT,Typeface.BOLD);label.setPadding(0,dp(12),0,dp(6));parent.addView(label);
        EditText v=new EditText(this);v.setHint(number?"0":"Enter "+hint.toLowerCase(Locale.ROOT));v.setTextSize(16);v.setTextColor(INK);v.setHintTextColor(MUTED);v.setSingleLine(true);v.setPadding(dp(14),dp(12),dp(14),dp(12));v.setBackground(surface(Color.rgb(249,251,252),10,LINE));v.setMinimumHeight(dp(52));if(number)v.setInputType(InputType.TYPE_CLASS_NUMBER);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.bottomMargin=dp(8);parent.addView(v,lp);return v;
    }
    private void button(LinearLayout parent,String label,Runnable action) {
        Button v=new Button(this);boolean secondary=label.startsWith("Discard")||label.startsWith("Choose")||label.startsWith("Edit")||label.startsWith("Load")||label.startsWith("View")||label.startsWith("Share");v.setText(label);v.setTextSize(15);v.setTypeface(Typeface.DEFAULT,Typeface.BOLD);v.setAllCaps(false);v.setTextColor(secondary?TEAL:Color.WHITE);v.setBackgroundTintList(null);v.setBackground(new android.graphics.drawable.RippleDrawable(ColorStateList.valueOf(secondary?0x22087f72:0x33ffffff),surface(secondary?Color.WHITE:TEAL,10,secondary?LINE:0),null));v.setMinHeight(dp(50));v.setMinimumHeight(dp(50));v.setPadding(dp(14),dp(10),dp(14),dp(10));LinearLayout.LayoutParams lp=parent.getOrientation()==LinearLayout.HORIZONTAL?new LinearLayout.LayoutParams(0,-2,1):new LinearLayout.LayoutParams(-1,-2);lp.topMargin=dp(10);lp.bottomMargin=dp(4);if(parent.getOrientation()==LinearLayout.HORIZONTAL){lp.leftMargin=dp(4);lp.rightMargin=dp(4);}parent.addView(v,lp);actions.add(v);v.setEnabled(!busy);v.setOnClickListener(x->{if(!busy)try{action.run();}catch(NumberFormatException e){show("Enter a valid whole-number quantity");}catch(Exception e){show(e.getMessage());}});
    }
    private void show(String s) { if(s==null)s="Unable to complete action";boolean working=busy;boolean ready=s.equals("Ready");statusBox.setVisibility(ready?View.GONE:View.VISIBLE);progress.setVisibility(working?View.VISIBLE:View.GONE);statusBox.setBackgroundColor(working?Color.rgb(229,244,241):Color.rgb(255,239,235));message.setTextColor(working?TEAL:Color.rgb(157,58,43));message.setText(s);if(dialogError!=null)dialogError.setText(working||ready?"":s);for(Button b:actions)b.setEnabled(!busy); }
    private JSONObject obj(Object... args) {
        JSONObject o=new JSONObject(); try { for(int i=0;i<args.length;i+=2)o.put((String)args[i],args[i+1]); } catch(JSONException e){throw new RuntimeException(e);} return o;
    }
    private void put(JSONObject data,String key,Object value) { try{data.put(key,value);}catch(JSONException e){throw new IllegalArgumentException(e);} }
    private void task(Work work,Reply reply) {
        if(busy)return; busy=true; show("Working…");
        worker.execute(()->{try{JSONObject value=work.run();runOnUiThread(()->{busy=false;try{reply.done(value);if(!busy)show("Ready");}catch(Exception e){show(e.getMessage());}});}catch(Exception e){runOnUiThread(()->{busy=false;if(e instanceof ApiFailure&&((ApiFailure)e).status==401&&!token.isEmpty()){token="";scan=null;photo=null;pendingKeys.clear();loginScreen();}show(e.getMessage());});}});
    }
    private JSONObject api(String path,JSONObject data) throws Exception {
        HttpURLConnection con=(HttpURLConnection)new URL(base+path).openConnection();
        con.setConnectTimeout(90000);con.setReadTimeout(120000);con.setRequestProperty("Authorization","Bearer "+token);
        try {
            if(data!=null){con.setRequestMethod("POST");con.setDoOutput(true);con.setRequestProperty("Content-Type","application/json");try(OutputStream out=con.getOutputStream()){out.write(data.toString().getBytes("UTF-8"));}}
            int code=con.getResponseCode(); InputStream stream=code<400?con.getInputStream():con.getErrorStream();
            if(stream==null)throw new IOException("The server returned no response (HTTP "+code+"). Check the server address.");
            String content;try(InputStream in=stream;ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);content=out.toString("UTF-8");}
            if(content.trim().isEmpty())throw new IOException("The server returned an empty response (HTTP "+code+").");
            JSONObject result;try{result=new JSONObject(content);}catch(JSONException e){throw new IOException("The server returned an invalid response (HTTP "+code+"). Check its address and hosting logs.");}
            if(code>=400)throw new ApiFailure(code,result.optString("error","Server error "+code));return result;
        } catch(SocketTimeoutException e) {
            throw new IOException("The hosted server took too long to respond. It may be waking up. "+(data!=null&&!path.equals("/login")?"The change may have been saved. Refresh inventory before retrying; keep the same quantities and reason for a safe retry.":"Wait a minute and try again."));
        } catch(UnknownHostException|ConnectException e) {
            throw new IOException("Cannot reach MOVIS cloud. Check Wi-Fi or mobile data and try again.");
        } finally {con.disconnect();}
    }
    private void loginScreen() {
        shell("Online warehouse inventory");
        TextView eyebrow=heading("YOUR WAREHOUSE, CONNECTED",12);eyebrow.setTextColor(TEAL);eyebrow.setPadding(0,dp(22),0,dp(4));body.addView(eyebrow);title("Welcome to MOVIS");note("Sign in to check stock, add items from a photo, and track returned goods.");
        LinearLayout form=card(body);form.addView(heading("Sign in",21));
        EditText user=field(form,"Username",false);user.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_NORMAL);user.setText(getPreferences(MODE_PRIVATE).getString("username",""));
        EditText password=field(form,"Password",false);password.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
        CheckBox reveal=new CheckBox(this);reveal.setText("Show password");reveal.setTextSize(14);reveal.setTextColor(MUTED);reveal.setButtonTintList(ColorStateList.valueOf(TEAL));form.addView(reveal);reveal.setOnCheckedChangeListener((b,on)->{int pos=password.getSelectionStart();password.setInputType(InputType.TYPE_CLASS_TEXT|(on?InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD:InputType.TYPE_TEXT_VARIATION_PASSWORD));password.setTypeface(Typeface.DEFAULT);password.setSelection(Math.max(0,pos));});
        TextView cloud=text("Connected to MOVIS cloud\n"+CLOUD_SERVER,14);cloud.setTextColor(TEAL);form.addView(cloud);
        TextView help=text("Use the administrator account created for your hosted system, or an account your administrator has added. Internet is required. The server may take a minute to wake up after inactivity.",14);help.setTextColor(MUTED);help.setVisibility(View.GONE);
        TextView helpLink=text("Sign-in help",14);helpLink.setTextColor(TEAL);helpLink.setPadding(0,dp(10),0,dp(10));form.addView(helpLink);form.addView(help);helpLink.setOnClickListener(v->help.setVisibility(help.getVisibility()==View.GONE?View.VISIBLE:View.GONE));
        button(form,"Sign in",()->{
            String userValue=user.getText().toString().trim(),passwordValue=password.getText().toString();base=CLOUD_SERVER;
            if(userValue.isEmpty()){user.setError("Enter your username");user.requestFocus();return;}if(passwordValue.isEmpty()){password.setError("Enter your password");password.requestFocus();return;}
            task(()->api("/login",obj("username",userValue,"password",passwordValue)),r->{token=r.getString("token");role=r.getString("role");username=r.getString("username");getPreferences(MODE_PRIVATE).edit().putString("server",base).putString("username",username).apply();((android.view.inputmethod.InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(password.getWindowToken(),0);loadInventory();});
        });
        note("Use Wi-Fi or mobile data. Your phone and web dashboard share the same inventory; your computer can be switched off.");
    }
    private void loadInventory() { task(()->api("/inventory",null),r->{inventory=r;home(current);}); }
    private boolean canWrite() { return role.equals("admin")||role.equals("operator"); }
    private void home(String tab) {
        current=tab;shell(username+" · "+(role.equals("admin")?"Administrator":role.equals("operator")?"Operator":"Viewer"));
        LinearLayout row=new LinearLayout(this);row.setBackgroundColor(Color.WHITE);row.setPadding(dp(6),dp(8),dp(6),dp(8));navigation.addView(row);
        for(String page:new String[]{"Inventory","Scan","Returns","Reports"}) {LinearLayout item=column();item.setGravity(Gravity.CENTER);boolean selected=page.equals(tab);item.setBackground(surface(selected?Color.rgb(226,242,238):Color.WHITE,12,0));item.addView(new NavIcon(page,selected?TEAL:MUTED),new LinearLayout.LayoutParams(dp(24),dp(24)));TextView label=text(page.equals("Scan")?"Photo":page,14);label.setTextColor(selected?TEAL:MUTED);label.setTypeface(Typeface.DEFAULT,selected?Typeface.BOLD:Typeface.NORMAL);item.addView(label);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(66),1);lp.leftMargin=dp(2);lp.rightMargin=dp(2);row.addView(item,lp);item.setContentDescription(page.equals("Scan")?"Photo scan":page);item.setOnClickListener(v->{if(!busy){if(page.equals("Inventory")){current=page;loadInventory();}else home(page);}});}
        if(inventory.optString("mode").equals("demo"))banner("Demo mode · Photo detections are samples until a trained model is connected.");
        switch(tab){case "Scan":scanScreen();break;case "Returns":returnsScreen();break;case "Reports":reportsScreen();break;case "Manage":manageScreen();break;default:inventoryScreen();}
    }
    private JSONArray array(String key){return inventory.optJSONArray(key)==null?new JSONArray():inventory.optJSONArray(key);}
    private Spinner selector(LinearLayout parent,JSONArray values,String label) {
        TextView caption=heading(label,14);caption.setPadding(0,dp(12),0,dp(8));parent.addView(caption);Spinner spinner=new Spinner(this);ArrayList<String> labels=new ArrayList<>();
        for(int i=0;i<values.length();i++)labels.add(values.optJSONObject(i).optString("name",values.optJSONObject(i).optString("sku")));
        ArrayAdapter<String> adapter=new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,labels);spinner.setAdapter(adapter);spinner.setBackground(surface(Color.WHITE,10,LINE));spinner.setPadding(dp(10),dp(6),dp(8),dp(6));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(54));lp.bottomMargin=dp(12);parent.addView(spinner,lp);return spinner;
    }
    private int selected(Spinner spinner,JSONArray values){int p=spinner.getSelectedItemPosition();if(p<0||p>=values.length())throw new IllegalArgumentException("Create an item and location first");return values.optJSONObject(p).optInt("id");}
    private String retryKey(String kind,JSONObject payload){String signature=kind+payload.toString();if(!pendingKeys.containsKey(signature))pendingKeys.put(signature,UUID.randomUUID().toString());return pendingKeys.get(signature);}
    private void inventoryScreen() {
        title("Inventory");note("Available stock across your warehouse locations.");JSONArray stock=array("stock");long units=0;for(int i=0;i<stock.length();i++)units+=stock.optJSONObject(i).optInt("quantity");
        LinearLayout totals=new LinearLayout(this);body.addView(totals);for(int i=0;i<2;i++){LinearLayout stat=column();stat.setPadding(dp(16),dp(14),dp(16),dp(14));stat.setBackground(surface(i==0?TEAL:Color.WHITE,14,i==0?0:LINE));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,-2,1);if(i==0)lp.rightMargin=dp(10);totals.addView(stat,lp);TextView count=heading(String.valueOf(i==0?units:array("items").length()),28);count.setTextColor(i==0?Color.WHITE:INK);TextView label=text(i==0?"Available units":"Products",14);label.setTextColor(i==0?Color.rgb(202,238,228):MUTED);stat.addView(count);stat.addView(label);}
        section("Stock by item");
        if(stock.length()==0){LinearLayout empty=card(body);empty.addView(heading("No stock yet",18));empty.addView(text(role.equals("admin")?"Open the account menu to create items and locations in Manage warehouse.":"Ask your administrator to register items and stock locations.",14));}
        for(int i=0;i<stock.length();i++){JSONObject item=stock.optJSONObject(i);LinearLayout box=card(body);LinearLayout line=new LinearLayout(this);line.setGravity(Gravity.CENTER_VERTICAL);LinearLayout details=column();details.addView(heading(item.optString("name"),18));TextView meta=text(item.optString("sku")+" · "+item.optString("location"),14);meta.setTextColor(MUTED);details.addView(meta);line.addView(details,new LinearLayout.LayoutParams(0,-2,1));TextView qty=heading(String.valueOf(item.optInt("quantity")),28);qty.setTextColor(item.optInt("quantity")==0?Color.rgb(164,65,49):TEAL);qty.setPadding(dp(12),0,0,0);line.addView(qty);box.addView(line);TextView available=text(item.optInt("quantity")==0?"Out of stock":"Available inventory",14);available.setTextColor(MUTED);box.addView(available);if(canWrite())button(box,"Edit quantity",()->manualEdit(item));}
    }
    private void manualEdit(JSONObject stock){
        LinearLayout form=column();form.setPadding(dp(18),dp(8),dp(18),dp(8));form.addView(text(stock.optString("name")+" • "+stock.optString("location"),16));
        EditText quantity=field(form,"New TOTAL available quantity",true);quantity.setText(String.valueOf(stock.optInt("quantity")));EditText reason=field(form,"Reason for manual change",false);
        dialogError=text("",14);dialogError.setTextColor(Color.rgb(157,58,43));form.addView(dialogError);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Edit stock quantity").setView(form).setNegativeButton("Cancel",null).setPositiveButton("Save",null).create();
        dialog.setOnDismissListener(ignored->dialogError=null);
        dialog.setOnShowListener(ignored->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{try{
            int qty=Integer.parseInt(quantity.getText().toString());String why=reason.getText().toString().trim();if(qty<0||why.isEmpty()){show("Use a nonnegative quantity and enter a reason");return;}
            JSONObject payload=obj("item_id",stock.optInt("item_id"),"location_id",stock.optInt("location_id"),"quantity",qty,"expected_version",stock.optInt("version"),"reason",why,"confirmed",true);put(payload,"request_key",retryKey("manual",payload));
            task(()->api("/manual-adjustments",payload),r->{dialog.dismiss();loadInventory();});
        }catch(Exception e){show("Enter a valid whole-number quantity");}}));dialog.show();
    }
    private void scanScreen() {
        final boolean reconcile=scanPurpose==1;
        title(reconcile?"Verify a complete count":"Add incoming goods");if(!canWrite()){note("Your role can view inventory and reports.");return;}
        LinearLayout purposes=new LinearLayout(this);body.addView(purposes);
        button(purposes,"Incoming goods",()->{scanPurpose=0;scan=null;photo=null;home("Scan");});
        button(purposes,"Complete count",()->{scanPurpose=1;scan=null;photo=null;home("Scan");});
        JSONArray locations=array("locations");Spinner location=selector(body,locations,reconcile?"Count at location":"Add stock to location");
        for(int i=0;i<locations.length();i++)if(locations.optJSONObject(i).optInt("id")==photoLocation)location.setSelection(i);
        note(reconcile?"Count ALL units for the selected item and location, including those outside the photograph. Visible detections are only a starting point. Hidden stock cannot be counted reliably.":"Take a photo of incoming goods, review the quantities, then add or discard. Add only items not already recorded.");
        LinearLayout photoActions=new LinearLayout(this);body.addView(photoActions);
        button(photoActions,"Take photo",()->{photoLocation=selected(location,locations);scan=null;photo=null;Intent intent=new Intent(MediaStore.ACTION_IMAGE_CAPTURE);Uri uri=Uri.parse("content://com.movis.warehouse.photos/capture.jpg");intent.putExtra(MediaStore.EXTRA_OUTPUT,uri);intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_READ_URI_PERMISSION);intent.setClipData(android.content.ClipData.newRawUri("MOVIS photo",uri));startActivityForResult(intent,101);});
        button(photoActions,"Choose photo",()->{photoLocation=selected(location,locations);scan=null;photo=null;Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.setType("image/*");intent.addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(intent,102);});
        if(photo!=null){body.addView(new DetectionView(photo,scan==null?new JSONArray():scan.optJSONArray("detections")),new LinearLayout.LayoutParams(-1,dp(250)));
            button(body,"Analyze photo",()->{
                if(selected(location,locations)!=photoLocation){show("Location changed. Choose or capture a new photo.");return;}
                scan=null;ByteArrayOutputStream output=new ByteArrayOutputStream();photo.compress(Bitmap.CompressFormat.JPEG,85,output);
                JSONObject payload=obj("location_id",photoLocation,"image",Base64.encodeToString(output.toByteArray(),Base64.NO_WRAP));
                task(()->api("/scans",payload),r->{scan=r;home("Scan");});
            });
        }
        if(scan!=null){section("Review detected items");note(scan.optString("warning"));note("Processing time: "+scan.optDouble("processing_ms")+" ms");
            JSONArray detections=scan.optJSONArray("detections");HashMap<Integer,Integer> counts=new HashMap<>();
            for(int i=0;i<detections.length();i++){JSONObject d=detections.optJSONObject(i);int item=d.optInt("item_id",-1);counts.put(item,counts.getOrDefault(item,0)+1);note(d.optString("name")+" • "+Math.round(d.optDouble("confidence")*100)+"% confidence"+(item<0?" • unmapped class":""));}
            JSONArray snapshot=scan.optJSONArray("snapshot");
            ArrayList<Integer> itemIds=new ArrayList<>();ArrayList<EditText> quantities=new ArrayList<>();ArrayList<CheckBox> selectedItems=new ArrayList<>();
            for(int i=0;i<snapshot.length();i++){JSONObject stock=snapshot.optJSONObject(i);int item=stock.optInt("item_id");String name="Item "+item;
                for(int j=0;j<array("items").length();j++)if(array("items").optJSONObject(j).optInt("id")==item)name=array("items").optJSONObject(j).optString("name");
                LinearLayout itemCard=card(body);CheckBox select=new CheckBox(this);select.setText(name);select.setTextSize(17);select.setTypeface(Typeface.DEFAULT,Typeface.BOLD);select.setButtonTintList(ColorStateList.valueOf(TEAL));select.setChecked(counts.getOrDefault(item,0)>0);itemCard.addView(select);TextView available=text(stock.optInt("quantity")+" currently available · "+counts.getOrDefault(item,0)+" detected",14);available.setTextColor(MUTED);itemCard.addView(available);
                EditText count=reconcile?new EditText(this):field(itemCard,"Quantity to add",true);count.setText(String.valueOf(counts.getOrDefault(item,0)));
                if(reconcile){count.setVisibility(View.GONE);select.setVisibility(View.GONE);button(itemCard,"Verify complete count for "+name,()->reconcileItem(stock,counts.getOrDefault(item,0)));}
                itemIds.add(item);quantities.add(count);selectedItems.add(select);
            }
            note(reconcile?"Choose one item to reconcile. The new total is saved only after you verify a complete physical count and review the difference.":"Select only the incoming items you want to add. You can correct missed detections or exclude incorrect ones. Unmapped classes must first be registered by an administrator.");
            if(!reconcile){EditText reason=field(body,"Reason / receipt reference",false);
            button(body,"Add selected items to inventory",()->{
                JSONArray lines=new JSONArray();int total=0;
                for(int i=0;i<itemIds.size();i++)if(selectedItems.get(i).isChecked()){int qty=Integer.parseInt(quantities.get(i).getText().toString());if(qty<1){show("Selected quantities must be at least 1");return;}lines.put(obj("item_id",itemIds.get(i),"quantity",qty));total+=qty;}
                if(lines.length()==0){show("Select at least one item, or discard the photo.");return;}
                String why=reason.getText().toString().trim();if(why.isEmpty()){show("Enter a reason or receipt reference");return;}
                JSONObject payload=obj("scan_id",scan.optString("id"),"items",lines,"reason",why,"confirmed",true);put(payload,"request_key",retryKey("photo-add",payload));
                new AlertDialog.Builder(this).setTitle("Add incoming stock?").setMessage("Add "+total+" new units across "+lines.length()+" selected items? Existing stock will increase by these quantities.").setNegativeButton("Cancel",null).setPositiveButton("Add to inventory",(d,w)->task(()->api("/scan-additions",payload),r->{scan=null;photo=null;loadInventory();})).show();
            });
            }
            button(body,"Discard — do not save",()->{scan=null;photo=null;home("Scan");});
        }
    }
    private void reconcileItem(JSONObject stock,int detected) {
        LinearLayout form=column();form.setPadding(dp(18),dp(8),dp(18),dp(8));
        form.addView(text("Recorded quantity: "+stock.optInt("quantity")+". Visible detections: "+detected+". Count the entire selected item/location before confirming.",15));
        EditText count=field(form,"Verified TOTAL quantity",true);count.setText(String.valueOf(detected));
        EditText reason=field(form,"Adjustment reason",false);
        CheckBox complete=new CheckBox(this);complete.setText("I physically checked the ENTIRE item/location, including units outside the photo.");form.addView(complete);
        dialogError=text("",14);dialogError.setTextColor(Color.rgb(157,58,43));form.addView(dialogError);
        final String scanId=scan.optString("id");
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Verify full stock count").setView(form).setNegativeButton("Cancel",null).setPositiveButton("Review adjustment",null).create();
        dialog.setOnDismissListener(v->dialogError=null);
        dialog.setOnShowListener(v->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(x->{try{
            int qty=Integer.parseInt(count.getText().toString());String why=reason.getText().toString().trim();
            if(qty<0||why.isEmpty()||!complete.isChecked()){show("Enter a quantity and reason, and confirm a complete physical count.");return;}
            JSONObject payload=obj("item_id",stock.optInt("item_id"),"location_id",photoLocation,"verified_quantity",qty,"scan_id",scanId,"reason",why,"confirmed",true,"complete_location_count",true);put(payload,"request_key",retryKey("reconcile",payload));
            new AlertDialog.Builder(this).setTitle("Confirm stock adjustment").setMessage("Previous: "+stock.optInt("quantity")+"\nVerified: "+qty+"\nDifference: "+(qty-stock.optInt("quantity"))+"\nSave this verified total?").setNegativeButton("Cancel",null).setPositiveButton("Save adjustment",(d,w)->task(()->api("/adjustments",payload),r->{dialog.dismiss();scan=null;photo=null;loadInventory();})).show();
        }catch(NumberFormatException e){show("Enter a valid whole-number quantity");}}));dialog.show();
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(result!=RESULT_OK)return;
        try{Uri uri=request==101?Uri.parse("content://com.movis.warehouse.photos/capture.jpg"):data.getData();
            task(()->{BitmapFactory.Options options=new BitmapFactory.Options();options.inJustDecodeBounds=true;try(InputStream in=getContentResolver().openInputStream(uri)){BitmapFactory.decodeStream(in,null,options);}if(options.outWidth<=0)throw new IOException("Unsupported photo");options.inSampleSize=1;while(Math.max(options.outWidth,options.outHeight)/options.inSampleSize>1600)options.inSampleSize*=2;options.inJustDecodeBounds=false;try(InputStream in=getContentResolver().openInputStream(uri)){photo=BitmapFactory.decodeStream(in,null,options);}if(photo==null)throw new IOException("Unable to decode photo");orientPhoto(uri);return obj();},r->{if(!token.isEmpty())home("Scan");});
        }catch(Exception e){show(e.getMessage());}
    }
    private void orientPhoto(Uri uri) throws IOException {
        int orientation=1;
        try(InputStream in=getContentResolver().openInputStream(uri)){orientation=new android.media.ExifInterface(in).getAttributeInt(android.media.ExifInterface.TAG_ORIENTATION,1);}catch(IOException ignored){}
        Matrix matrix=new Matrix();
        switch(orientation){case 2:matrix.setScale(-1,1);break;case 3:matrix.setRotate(180);break;case 4:matrix.setScale(1,-1);break;case 5:matrix.setRotate(90);matrix.postScale(-1,1);break;case 6:matrix.setRotate(90);break;case 7:matrix.setRotate(-90);matrix.postScale(-1,1);break;case 8:matrix.setRotate(-90);break;default:return;}
        Bitmap oriented=Bitmap.createBitmap(photo,0,0,photo.getWidth(),photo.getHeight(),matrix,true);
        if(oriented!=photo){photo.recycle();photo=oriented;}
    }
    private void returnsScreen() {
        title("Returns");note("Track returned goods from inspection to restocking.");
        if(canWrite()){
            LinearLayout form=card(body);form.addView(heading("Record a return",19));
            Spinner item=selector(form,array("items"),"Returned item"),location=selector(form,array("locations"),"Restock destination");EditText qty=field(form,"Returned quantity",true),reason=field(form,"Return reason",false);
            button(form,"Record pending return",()->{
                JSONObject payload=obj("item_id",selected(item,array("items")),"location_id",selected(location,array("locations")),"quantity",Integer.parseInt(qty.getText().toString()),"reason",reason.getText().toString());String signature="return"+payload.toString();put(payload,"request_key",retryKey("return",payload));task(()->api("/returns",payload),r->{pendingKeys.remove(signature);home("Returns");});
            });
        }
        section("Return records");LinearLayout list=column();body.addView(list);
        button(body,"Load return records",()->task(()->api("/reports/returns",null),r->{list.removeAllViews();JSONArray rows=r.getJSONArray("rows");if(rows.length()==0){LinearLayout empty=card(list);empty.addView(heading("No returns recorded",18));empty.addView(text("New return records will appear here.",14));}
            for(int i=0;i<rows.length();i++){JSONObject ret=rows.getJSONObject(i);LinearLayout box=card(list);box.addView(heading(ret.optString("name")+" × "+ret.optInt("quantity"),18));TextView meta=text("Return #"+ret.optInt("id")+" · "+ret.optString("location"),14);meta.setTextColor(MUTED);box.addView(meta);TextView status=text(ret.optString("status"),14);status.setTypeface(Typeface.DEFAULT,Typeface.BOLD);status.setTextColor(ret.optString("status").equals("damaged")?Color.rgb(164,65,49):TEAL);box.addView(status);box.addView(text(ret.optString("reason"),14));
                if(canWrite()){String state=ret.optString("status");if(state.equals("pending inspection")){statusButton(box,ret,"accepted");statusButton(box,ret,"damaged");}else if(state.equals("accepted")){statusButton(box,ret,"returned to available stock");statusButton(box,ret,"damaged");}}
            }
        }));
    }
    private void statusButton(LinearLayout parent,JSONObject ret,String target){String label=target.equals("accepted")?"Accept after inspection":target.equals("damaged")?"Mark as damaged":"Restock accepted items";button(parent,label,()->{Runnable commit=()->task(()->api("/returns/"+ret.optInt("id"),obj("status",target,"confirmed_suitable",target.equals("returned to available stock"))),r->{current="Returns";loadInventory();});new AlertDialog.Builder(this).setTitle("Confirm return status").setMessage(target.equals("returned to available stock")?"I inspected these items and confirm they are suitable for available stock. Restock "+ret.optInt("quantity")+" units?":"Change return #"+ret.optInt("id")+" to "+target+"?").setNegativeButton("Cancel",null).setPositiveButton("Confirm",(d,w)->commit.run()).show();});}
    private String reportTitle(String type){switch(type){case "inventory":return "Available inventory";case "scans":return "Photo scans";case "adjustments":return "Inventory changes";case "returns":return "Returned goods";case "return_events":return "Return status history";default:return "Stock movements";}}
    private String itemName(int id){for(int i=0;i<array("items").length();i++){JSONObject item=array("items").optJSONObject(i);if(item.optInt("id")==id)return item.optString("name");}return "Item #"+id;}
    private String locationName(int id){for(int i=0;i<array("locations").length();i++){JSONObject location=array("locations").optJSONObject(i);if(location.optInt("id")==id)return location.optString("name");}return "Location #"+id;}
    private void reportRows(LinearLayout target,String kind,JSONArray rows){target.removeAllViews();if(rows.length()==0){target.addView(text("No records yet",15));return;}for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);TextView line=heading(kind.equals("scans")?"Photo scan · "+row.optString("mode").toUpperCase(Locale.ROOT):kind.equals("return_events")?"Return #"+row.optInt("return_id"):row.optString("name",itemName(row.optInt("item_id"))),16);target.addView(line);String details;
        switch(kind){case "inventory":details=row.optInt("quantity")+" available · "+row.optString("location");break;case "scans":details="Location: "+locationName(row.optInt("location_id"))+" · "+row.optString("id");break;case "adjustments":details="Previous "+row.optInt("previous_quantity")+" · New "+row.optInt("verified_quantity")+" · Change "+(row.optInt("difference")>0?"+":"")+row.optInt("difference")+"\n"+row.optString("reason");break;case "returns":details=row.optInt("quantity")+" units · "+row.optString("status")+"\n"+row.optString("reason");break;case "return_events":details=row.optString("new_status");break;default:details=row.optString("source_type")+" · Change "+(row.optInt("difference")>0?"+":"")+row.optInt("difference")+" · Balance "+row.optInt("resulting_quantity");}
        target.addView(text(details,14));if(!kind.equals("inventory")){TextView meta=text(row.optString("username")+" · "+row.optString("created_at").replace('T',' '),12);meta.setTextColor(MUTED);target.addView(meta);}View divider=new View(this);divider.setBackgroundColor(LINE);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(1));lp.topMargin=dp(8);lp.bottomMargin=dp(12);target.addView(divider,lp);}}
    private void reportsScreen(){title("Reports");note("Review warehouse records or share a CSV report.");for(String type:new String[]{"inventory","scans","adjustments","returns","return_events","movements"}){
        LinearLayout box=card(body);box.addView(heading(reportTitle(type),19));LinearLayout report=column();LinearLayout buttons=new LinearLayout(this);box.addView(buttons);
        button(buttons,"View report",()->task(()->api("/reports/"+type,null),r->reportRows(report,type,r.getJSONArray("rows"))));
        button(buttons,"Share CSV",()->task(()->api("/reports/"+type,null),r->{JSONArray rows=r.getJSONArray("rows");StringBuilder csv=new StringBuilder();if(rows.length()>0){ArrayList<String> keys=new ArrayList<>();rows.getJSONObject(0).keys().forEachRemaining(keys::add);csv.append(csvRow(keys));for(int i=0;i<rows.length();i++){ArrayList<String> values=new ArrayList<>();for(String key:keys)values.add(rows.getJSONObject(i).optString(key));csv.append(csvRow(values));}}Intent share=new Intent(Intent.ACTION_SEND);share.setType("text/csv");share.putExtra(Intent.EXTRA_SUBJECT,"MOVIS "+reportTitle(type));share.putExtra(Intent.EXTRA_TEXT,csv.toString());startActivity(Intent.createChooser(share,"Share report"));}));box.addView(report);
    }}
    private String csvRow(List<String> cells){StringJoiner row=new StringJoiner(",");for(String cell:cells){if(cell.matches("^[=+@\\-\\t\\r].*"))cell="'"+cell;row.add("\""+cell.replace("\"","\"\"")+"\"");}return row+"\r\n";}
    private void manageScreen(){title("Manage warehouse");note("Create your real items later. Model class must exactly match its label in the training dataset. New stock starts at zero and changes through verified adjustments or inspected returns.");
        section("Products");
        EditText sku=field(body,"SKU",false),name=field(body,"Item name",false),cls=field(body,"YOLO class name",false);
        button(body,"Create item",()->task(()->api("/catalog",obj("kind","item","sku",sku.getText().toString(),"name",name.getText().toString(),"model_class",cls.getText().toString())),r->loadInventory()));
        Spinner editItem=selector(body,array("items"),"Existing item to edit");
        button(body,"Load item into fields",()->{int id=selected(editItem,array("items"));for(int i=0;i<array("items").length();i++){JSONObject value=array("items").optJSONObject(i);if(value.optInt("id")==id){sku.setText(value.optString("sku"));name.setText(value.optString("name"));cls.setText(value.optString("model_class"));}}});
        button(body,"Save selected item",()->{JSONObject payload=obj("kind","update_item","id",selected(editItem,array("items")),"sku",sku.getText().toString(),"name",name.getText().toString(),"model_class",cls.getText().toString());task(()->api("/catalog",payload),r->loadInventory());});
        section("Locations");
        EditText loc=field(body,"Location name (shelf or bin)",false);button(body,"Create location",()->task(()->api("/catalog",obj("kind","location","name",loc.getText().toString())),r->loadInventory()));
        section("Register stock");
        Spinner items=selector(body,array("items"),"Register stock item"),locations=selector(body,array("locations"),"Register stock location");button(body,"Register zero-stock record",()->task(()->api("/catalog",obj("kind","stock","item_id",selected(items,array("items")),"location_id",selected(locations,array("locations")))),r->loadInventory()));
        section("User accounts");
        EditText user=field(body,"New username",false),password=field(body,"New password (12–128 characters)",false);password.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
        Spinner roles=new Spinner(this);roles.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"operator","viewer","admin"}));body.addView(roles);button(body,"Create user",()->task(()->api("/users",obj("username",user.getText().toString(),"password",password.getText().toString(),"role",roles.getSelectedItem().toString())),r->home("Manage")));
    }
    private class NavIcon extends View {
        final String name;final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);
        NavIcon(String name,int color){super(MainActivity.this);this.name=name;p.setColor(color);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(dp(2));p.setStrokeCap(Paint.Cap.ROUND);}
        @Override protected void onDraw(Canvas c){super.onDraw(c);c.save();c.scale(getWidth()/24f,getHeight()/24f);p.setStrokeWidth(1.8f);if(name.equals("Scan")){c.drawRoundRect(3,6,21,20,3,3,p);c.drawCircle(12,13,4,p);c.drawLine(8,6,9,3,p);c.drawLine(9,3,15,3,p);c.drawLine(15,3,16,6,p);}else if(name.equals("Inventory")){c.drawRoundRect(3,3,21,21,2,2,p);c.drawLine(3,9,21,9,p);c.drawLine(12,9,12,21,p);}else if(name.equals("Returns")){c.drawArc(4,4,20,20,40,280,false,p);c.drawLine(4,6,4,12,p);c.drawLine(4,12,10,12,p);}else{c.drawRoundRect(4,2,20,22,2,2,p);c.drawLine(8,7,16,7,p);c.drawLine(8,12,16,12,p);c.drawLine(8,17,13,17,p);}c.restore();}
    }
    private class DetectionView extends View {
        Bitmap bitmap;JSONArray boxes;Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        DetectionView(Bitmap b,JSONArray detections){super(MainActivity.this);bitmap=b;boxes=detections==null?new JSONArray():detections;}
        @Override protected void onDraw(Canvas canvas){super.onDraw(canvas);float scale=Math.min(getWidth()/(float)bitmap.getWidth(),getHeight()/(float)bitmap.getHeight());float width=bitmap.getWidth()*scale,height=bitmap.getHeight()*scale,x=(getWidth()-width)/2,y=(getHeight()-height)/2;paint.setStyle(Paint.Style.FILL);canvas.drawBitmap(bitmap,null,new RectF(x,y,x+width,y+height),paint);
            for(int i=0;i<boxes.length();i++){JSONObject d=boxes.optJSONObject(i);JSONArray b=d.optJSONArray("box");if(b==null)continue;paint.setColor(TEAL);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(dp(2));float left=x+(float)b.optDouble(0)*width,top=y+(float)b.optDouble(1)*height;canvas.drawRect(left,top,x+(float)b.optDouble(2)*width,y+(float)b.optDouble(3)*height,paint);paint.setStyle(Paint.Style.FILL);paint.setTextSize(dp(12));canvas.drawText(d.optString("name")+" "+Math.round(d.optDouble("confidence")*100)+"%",left,Math.max(dp(14),top-dp(3)),paint);}}
    }
}
