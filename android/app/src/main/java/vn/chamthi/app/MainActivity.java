package vn.chamthi.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.view.View;
import android.view.Window;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.core.content.FileProvider;
import androidx.webkit.WebViewAssetLoader;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Arrays;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.util.ArrayList;

/**
 * App Chấm Thi: bọc trang web (assets/index.html) trong WebView.
 * Trang được phục vụ qua https://appassets.androidplatform.net để có "ngữ cảnh bảo mật",
 * nhờ đó camera trực tiếp (tự động quét) và IndexedDB (lưu dữ liệu) hoạt động.
 */
public class MainActivity extends Activity {
    private static final int REQ_FILE = 11;
    private static final int REQ_CAM_PERM = 21;
    private static final String START_URL = "https://appassets.androidplatform.net/app/index.html";
    // Bản web mới nhất trên GitHub (nhánh webapp) và số phiên bản lõi Android (nhánh apk)
    private static final String WEB_URL = "https://raw.githubusercontent.com/HatThi32/CHAMTHI-TN/webapp/index.html";
    private static final String NATIVE_VER_URL = "https://raw.githubusercontent.com/HatThi32/CHAMTHI-TN/apk/version.txt";
    private static final String APK_URL = "https://github.com/HatThi32/CHAMTHI-TN/raw/apk/ChamThi.apk";

    private WebView web;
    private ValueCallback<Uri[]> fileCallback;
    private Uri cameraOutput;
    private PermissionRequest pendingWebPermission;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Window w = getWindow();
        w.setStatusBarColor(Color.parseColor("#16382D"));
        w.setNavigationBarColor(Color.parseColor("#16382D"));

        web = new WebView(this);
        setContentView(web);

        final WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .addPathHandler("/app/", path -> {
                    // Ưu tiên bản web đã tự cập nhật, nếu chưa có thì dùng bản đi kèm APK
                    try {
                        File f = updatedFile();
                        InputStream in = f.exists() && f.length() > 100000 ? new FileInputStream(f) : getAssets().open("index.html");
                        return new WebResourceResponse("text/html", "utf-8", in);
                    } catch (Exception e) { return null; }
                })
                .build();

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setTextZoom(100);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return loader.shouldInterceptRequest(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                if ("appassets.androidplatform.net".equals(u.getHost())) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) { }
                return true;
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(() -> {
                    if (hasCamera()) {
                        request.grant(request.getResources());
                    } else {
                        pendingWebPermission = request;
                        requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAM_PERM);
                    }
                });
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                boolean imagesOnly = false;
                String[] types = params.getAcceptTypes();
                if (types != null) for (String t : types) if (t != null && t.startsWith("image")) imagesOnly = true;
                try {
                    Intent intent;
                    if (params.isCaptureEnabled() && imagesOnly && hasCamera()) {
                        File dir = new File(getCacheDir(), "camera");
                        dir.mkdirs();
                        File f = new File(dir, "phieu_" + System.currentTimeMillis() + ".jpg");
                        cameraOutput = FileProvider.getUriForFile(MainActivity.this, getPackageName() + ".files", f);
                        intent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
                        intent.putExtra(MediaStore.EXTRA_OUTPUT, cameraOutput);
                        intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    } else {
                        cameraOutput = null;
                        intent = new Intent(Intent.ACTION_GET_CONTENT);
                        intent.addCategory(Intent.CATEGORY_OPENABLE);
                        intent.setType(imagesOnly ? "image/*" : "*/*");
                        if (params.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE)
                            intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                        intent = Intent.createChooser(intent, "Chọn tệp");
                    }
                    startActivityForResult(intent, REQ_FILE);
                } catch (Exception e) {
                    fileCallback = null;
                    Toast.makeText(MainActivity.this, "Không mở được trình chọn tệp", Toast.LENGTH_LONG).show();
                    return false;
                }
                return true;
            }
        });

        web.addJavascriptInterface(new Bridge(), "AndroidBridge");
        if (!hasCamera()) requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAM_PERM);
        web.loadUrl(START_URL);
        checkUpdates();
    }

    private File updatedFile() { return new File(new File(getFilesDir(), "web"), "index.html"); }

    private static byte[] download(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url + "?t=" + System.currentTimeMillis()).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(30000);
        c.setUseCaches(false);
        if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
        try (InputStream in = c.getInputStream(); ByteArrayOutputStream bo = new ByteArrayOutputStream()) {
            byte[] buf = new byte[65536];
            int n;
            while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
            return bo.toByteArray();
        }
    }

    private byte[] currentWeb() {
        try {
            File f = updatedFile();
            InputStream in = f.exists() && f.length() > 100000 ? new FileInputStream(f) : getAssets().open("index.html");
            try (ByteArrayOutputStream bo = new ByteArrayOutputStream()) {
                byte[] buf = new byte[65536];
                int n;
                while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
                in.close();
                return bo.toByteArray();
            }
        } catch (Exception e) { return new byte[0]; }
    }

    /** Tự cập nhật: tải bản web mới nhất; báo khi có bản APK lõi mới. Không có mạng thì bỏ qua. */
    private void checkUpdates() {
        new Thread(() -> {
            try {
                byte[] fresh = download(WEB_URL);
                String head = new String(fresh, 0, Math.min(fresh.length, 4000), "UTF-8");
                if (fresh.length > 100000 && head.contains("Chấm Thi") && !Arrays.equals(fresh, currentWeb())) {
                    File dir = new File(getFilesDir(), "web");
                    dir.mkdirs();
                    File tmp = new File(dir, "index.html.tmp");
                    try (FileOutputStream os = new FileOutputStream(tmp)) { os.write(fresh); }
                    if (tmp.renameTo(updatedFile()))
                        runOnUiThread(() -> web.evaluateJavascript("window.__ctUpdated&&window.__ctUpdated()", null));
                }
            } catch (Exception ignored) { }
            try {
                int latest = Integer.parseInt(new String(download(NATIVE_VER_URL), "UTF-8").trim());
                int mine = getPackageManager().getPackageInfo(getPackageName(), 0).versionCode;
                if (latest > mine) runOnUiThread(() -> new AlertDialog.Builder(MainActivity.this)
                        .setTitle("Có bản cài đặt mới")
                        .setMessage("Đã có app Chấm Thi bản " + latest + " (máy đang dùng bản " + mine + "). Tải về và cài đè lên, dữ liệu vẫn giữ nguyên.")
                        .setPositiveButton("Tải về", (d, w) -> {
                            try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(APK_URL))); } catch (Exception ignored) { }
                        })
                        .setNegativeButton("Để sau", null)
                        .show());
            } catch (Exception ignored) { }
        }).start();
    }

    private boolean hasCamera() {
        return checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED;
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode == REQ_CAM_PERM && pendingWebPermission != null) {
            if (results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED)
                pendingWebPermission.grant(pendingWebPermission.getResources());
            else pendingWebPermission.deny();
            pendingWebPermission = null;
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQ_FILE || fileCallback == null) return;
        Uri[] result = null;
        if (resultCode == RESULT_OK) {
            if (cameraOutput != null) {
                result = new Uri[]{cameraOutput};
            } else if (data != null) {
                if (data.getClipData() != null) {
                    ArrayList<Uri> list = new ArrayList<>();
                    for (int i = 0; i < data.getClipData().getItemCount(); i++)
                        list.add(data.getClipData().getItemAt(i).getUri());
                    result = list.toArray(new Uri[0]);
                } else if (data.getData() != null) {
                    result = new Uri[]{data.getData()};
                }
            }
        }
        fileCallback.onReceiveValue(result);
        fileCallback = null;
        cameraOutput = null;
    }

    @Override
    public void onBackPressed() {
        web.evaluateJavascript("(window.__ctBack?window.__ctBack():false)", value -> {
            if (!"true".equals(value)) MainActivity.super.onBackPressed();
        });
    }

    private static String mimeOf(String name) {
        String n = name.toLowerCase();
        if (n.endsWith(".pdf")) return "application/pdf";
        if (n.endsWith(".png")) return "image/png";
        if (n.endsWith(".jpg") || n.endsWith(".jpeg")) return "image/jpeg";
        if (n.endsWith(".xlsx")) return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
        if (n.endsWith(".zip")) return "application/zip";
        if (n.endsWith(".json")) return "application/json";
        return "application/octet-stream";
    }

    /** Cầu nối để trang web lưu tệp (bảng điểm, phiếu, ảnh) vào thư mục Tải xuống/ChamThi. */
    private class Bridge {
        @JavascriptInterface
        public String saveFile(String name, String base64) {
            try {
                byte[] bytes = Base64.decode(base64, Base64.DEFAULT);
                String mime = mimeOf(name);
                if (Build.VERSION.SDK_INT >= 29) {
                    ContentResolver cr = getContentResolver();
                    ContentValues v = new ContentValues();
                    v.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
                    v.put(MediaStore.MediaColumns.MIME_TYPE, mime);
                    v.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/ChamThi");
                    Uri uri = cr.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
                    if (uri == null) throw new Exception("không tạo được tệp");
                    try (OutputStream os = cr.openOutputStream(uri)) { os.write(bytes); }
                } else {
                    File dir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "ChamThi");
                    dir.mkdirs();
                    try (FileOutputStream os = new FileOutputStream(new File(dir, name))) { os.write(bytes); }
                }
                return "Đã lưu " + name + " vào Tải xuống/ChamThi";
            } catch (Exception e) {
                return "Không lưu được tệp: " + e.getMessage();
            }
        }

        @JavascriptInterface
        public void shareFile(String name, String base64) {
            try {
                byte[] bytes = Base64.decode(base64, Base64.DEFAULT);
                File dir = new File(getCacheDir(), "share");
                dir.mkdirs();
                File f = new File(dir, name);
                try (FileOutputStream os = new FileOutputStream(f)) { os.write(bytes); }
                Uri uri = FileProvider.getUriForFile(MainActivity.this, getPackageName() + ".files", f);
                Intent i = new Intent(Intent.ACTION_SEND);
                i.setType(mimeOf(name));
                i.putExtra(Intent.EXTRA_STREAM, uri);
                i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                runOnUiThread(() -> startActivity(Intent.createChooser(i, "Gửi " + name)));
            } catch (Exception e) {
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "Không gửi được tệp", Toast.LENGTH_LONG).show());
            }
        }
    }
}
