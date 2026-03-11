import Flutter
import AVFoundation
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    configureAudioSession()
    GeneratedPluginRegistrant.register(with: self)
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  private func configureAudioSession() {
    do {
      let session = AVAudioSession.sharedInstance()
      try session.setCategory(
        .playAndRecord,
        options: [.defaultToSpeaker, .allowBluetooth]
      )
      try session.setMode(.voiceChat)
      try session.setActive(true)
    } catch {
      NSLog("Audio session configuration failed: \(error)")
    }
  }
}
