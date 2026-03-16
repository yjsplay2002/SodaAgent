# Firebase Google Login Setup

This repository now uses Firebase Auth for Google sign-in on Flutter web and
mobile, plus Firebase ID token verification on the backend.

## Current project

- Firebase project display name: `SodaAgent`
- Firebase project ID: `sodaagent`
- Console: `https://console.firebase.google.com/project/sodaagent/overview`

Registered apps:

- Web app ID: `1:617391978945:web:cd5fe70cf785d766859740`
- Android app ID: `1:617391978945:android:e2a07bb9f9e99180859740`
- iOS app ID: `1:617391978945:ios:ba92b5b9f1ff5507859740`

## What is already wired

- Flutter app bootstraps Firebase from Dart defines.
- Android debug SHA-1 and SHA-256 were added to the Firebase Android app.
- Android uses `google-services.json` and the Google Services Gradle plugin.
- iOS uses `GoogleService-Info.plist` in the Xcode project.
- Backend verifies Firebase ID tokens on `/api/auth/session`.
- Backend issues short-lived WebSocket tickets for `/ws/mobile`.
- Session list/detail APIs now require `Authorization: Bearer <firebase-id-token>`.
- Firebase Auth Google provider is enabled.
- Authorized domains include `localhost` and `127.0.0.1` for local web sign-in.

## Local-only config files

Do not commit the real Firebase client config files. Keep these local only:

- `mobile/firebase_config.json`
- `mobile/android/app/google-services.json`
- `mobile/ios/Runner/GoogleService-Info.plist`

This repository keeps only:

- `mobile/firebase_config.example.json`
- the setup instructions in this document

To recreate the local files:

1. Copy `mobile/firebase_config.example.json` to `mobile/firebase_config.json` and fill in the real Firebase values.
2. Download the Android `google-services.json` from the Firebase console and place it at `mobile/android/app/google-services.json`.
3. Download the iOS `GoogleService-Info.plist` from the Firebase console and place it at `mobile/ios/Runner/GoogleService-Info.plist`.

Firebase console paths:

- Project settings > Your apps > Web / Android / iOS
- Authentication > Settings > Authorized domains
- Authentication > Sign-in method > Google

## Build commands

Use your local Firebase config file when building Flutter:

```powershell
C:\dev\flutter\bin\flutter.bat build web --release --dart-define-from-file=firebase_config.json
C:\dev\flutter\bin\flutter.bat build apk --release --dart-define-from-file=firebase_config.json
```

## Backend environment

The backend needs Firebase Admin credentials to verify Firebase ID tokens.

Set at least one of these before starting FastAPI:

- `FIREBASE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_APPLICATION_CREDENTIALS`

Recommended supporting variables:

- `FIREBASE_PROJECT_ID=sodaagent`
- `FIREBASE_STORAGE_BUCKET=sodaagent.firebasestorage.app`

## iOS note

The first downloaded iOS plist was generated before the Google provider was
enabled, so it did not yet contain Google sign-in client ID fields. This repo
has now been updated with the latest iOS plist and reversed client ID URL
scheme.
