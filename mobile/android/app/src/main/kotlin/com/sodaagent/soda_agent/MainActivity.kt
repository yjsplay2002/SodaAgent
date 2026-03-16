package com.sodaagent.soda_agent

import android.Manifest
import android.content.pm.PackageManager
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.baseflow.geolocator.GeolocatorPlugin
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugins.pathprovider.PathProviderPlugin
import xyz.canardoux.fluttersound.FlutterSound

class MainActivity : FlutterActivity() {
    private var pendingPermissionResult: MethodChannel.Result? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        if (!flutterEngine.plugins.has(FlutterSound::class.java)) {
            flutterEngine.plugins.add(FlutterSound())
        }
        if (!flutterEngine.plugins.has(GeolocatorPlugin::class.java)) {
            flutterEngine.plugins.add(GeolocatorPlugin())
        }
        if (!flutterEngine.plugins.has(PathProviderPlugin::class.java)) {
            flutterEngine.plugins.add(PathProviderPlugin())
        }

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            "com.sodaagent.soda_agent/permissions",
        ).setMethodCallHandler(::handlePermissionCall)
    }

    private fun handlePermissionCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "hasRecordAudioPermission" -> result.success(hasRecordAudioPermission())
            "requestRecordAudioPermission" -> {
                if (hasRecordAudioPermission()) {
                    result.success(true)
                    return
                }

                if (pendingPermissionResult != null) {
                    result.error(
                        "permission_in_progress",
                        "A microphone permission request is already in progress.",
                        null,
                    )
                    return
                }

                pendingPermissionResult = result
                ActivityCompat.requestPermissions(
                    this,
                    arrayOf(Manifest.permission.RECORD_AUDIO),
                    REQUEST_RECORD_AUDIO_PERMISSION,
                )
            }
            else -> result.notImplemented()
        }
    }

    private fun hasRecordAudioPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.RECORD_AUDIO,
        ) == PackageManager.PERMISSION_GRANTED
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)

        if (requestCode != REQUEST_RECORD_AUDIO_PERMISSION) {
            return
        }

        val granted = grantResults.isNotEmpty() &&
            grantResults[0] == PackageManager.PERMISSION_GRANTED
        pendingPermissionResult?.success(granted)
        pendingPermissionResult = null
    }

    companion object {
        private const val REQUEST_RECORD_AUDIO_PERMISSION = 2001
    }
}
