package com.movis.warehouse;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.hardware.Camera;
import android.os.Bundle;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.*;

/** In-app rear-camera capture. There is no gallery import, pinch zoom or zoom control. */
@SuppressWarnings("deprecation")
public class CameraActivity extends Activity implements SurfaceHolder.Callback {
    private Camera camera;
    private SurfaceView preview;
    private Button shutter;
    private TextView status;
    private boolean taking=false;
    private SurfaceHolder ready;
    @Override public void onCreate(Bundle s){super.onCreate(s);LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setPadding(16,16,16,16);status=new TextView(this);status.setText("Main rear camera · 1× · Zoom disabled\nCapture different sacks; avoid overlapping groups.");root.addView(status);preview=new SurfaceView(this);root.addView(preview,new LinearLayout.LayoutParams(-1,0,1));shutter=new Button(this);shutter.setText("Capture new image");root.addView(shutter);setContentView(root);shutter.setEnabled(false);preview.getHolder().addCallback(this);preview.setOnTouchListener((v,event)->true);shutter.setOnClickListener(v->{if(camera==null||taking)return;taking=true;shutter.setEnabled(false);try{camera.takePicture(null,null,(bytes,c)->{try(FileOutputStream out=new FileOutputStream(new File(getCacheDir(),"capture.jpg"))){out.write(bytes);setResult(RESULT_OK);finish();}catch(IOException e){status.setText("Capture failed. Try again.");taking=false;camera.startPreview();shutter.setEnabled(true);}});}catch(RuntimeException e){status.setText("Camera capture failed. Reopen the camera.");taking=false;}});if(checkSelfPermission(Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.CAMERA},7);}
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results){super.onRequestPermissionsResult(request,permissions,results);if(request==7){if(results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED){if(ready!=null)start(ready);}else{status.setText("Camera permission is required to take new MOVIS images.");}}}
    public void surfaceCreated(SurfaceHolder h){ready=h;if(checkSelfPermission(Manifest.permission.CAMERA)==PackageManager.PERMISSION_GRANTED)start(h);}
    public void surfaceChanged(SurfaceHolder h,int format,int w,int height){}
    public void surfaceDestroyed(SurfaceHolder h){ready=null;release();}
    void start(SurfaceHolder h){if(camera!=null)return;try{int id=-1;Camera.CameraInfo info=new Camera.CameraInfo();for(int i=0;i<Camera.getNumberOfCameras();i++){Camera.getCameraInfo(i,info);if(info.facing==Camera.CameraInfo.CAMERA_FACING_BACK){id=i;break;}}if(id<0)throw new IOException("No rear camera available");camera=Camera.open(id);Camera.Parameters p=camera.getParameters();if(p.isZoomSupported())p.setZoom(0);List<String> modes=p.getSupportedFocusModes();if(modes!=null&&modes.contains(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE))p.setFocusMode(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE);Camera.Size size=null;for(Camera.Size s:p.getSupportedPictureSizes()){if(s.width*s.height<=4000000&&(size==null||s.width*s.height>size.width*size.height))size=s;}if(size!=null)p.setPictureSize(size.width,size.height);Camera.getCameraInfo(id,info);int rotation=getWindowManager().getDefaultDisplay().getRotation(),degrees=rotation==Surface.ROTATION_90?90:rotation==Surface.ROTATION_180?180:rotation==Surface.ROTATION_270?270:0;camera.setDisplayOrientation((info.orientation-degrees+360)%360);p.setRotation((info.orientation+degrees)%360);camera.setParameters(p);camera.setPreviewDisplay(h);camera.startPreview();shutter.setEnabled(true);}catch(Exception e){status.setText("Cannot open rear camera: "+e.getMessage());release();}}
    @Override protected void onPause(){super.onPause();release();}
    @Override protected void onResume(){super.onResume();if(ready!=null&&checkSelfPermission(Manifest.permission.CAMERA)==PackageManager.PERMISSION_GRANTED)start(ready);}
    void release(){if(camera!=null){camera.release();camera=null;}if(shutter!=null)shutter.setEnabled(false);}
}
