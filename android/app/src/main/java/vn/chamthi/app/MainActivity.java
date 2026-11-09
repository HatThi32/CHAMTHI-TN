package vn.chamthi.app;

import android.Manifest;
import android.app.Activity;
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

import java.io.File;
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
    private static final String START_URL = "https://appassets.androidplatform.net/assets/index.html";

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
