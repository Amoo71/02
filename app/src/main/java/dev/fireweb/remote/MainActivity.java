package dev.fireweb.remote;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.view.Gravity;
import android.widget.TextView;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        TextView view = new TextView(this);
        view.setText("Fire Web Remote is running\n\nOpen http://FIRE-TV-IP:8765 on your phone.\n\nThe service will continue in the background.");
        view.setTextColor(Color.WHITE);
        view.setTextSize(22);
        view.setGravity(Gravity.CENTER);
        view.setPadding(48, 48, 48, 48);
        setContentView(view);

        Intent service = new Intent(this, FireWebService.class);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(service);
        else startService(service);

        new Handler().postDelayed(new Runnable() {
            @Override
            public void run() {
                moveTaskToBack(true);
            }
        }, 1300);
    }
}
