# Android release, signing and direct APK distribution

The debug validation APK proves an earlier build compiled; it is not a signed
production release. No release build, signing-key generation, APK publication or
Android App Link verification has run. The user runs build/signing commands.

## Configure the real server

Copy the generated Android configuration example to ignored android/deployment.properties,
using your actual IP origin and PUBLIC certificate. Never use the server private
key. prepare_android.py scopes that certificate to the host and rejects HTTP.
For a publicly trusted domain later, remove server.certificate. Keep the configurable
URLs; no hardcoded real server address or secret belongs in source.

## Create the signing key once

Keep one private key for every future update. Losing/changing it prevents ordinary
updates to already-installed APKs. Store it outside the repository and back it up
separately in protected storage. Do not include it in routine directory-data backups.

```bash
install -d -m 700 "$HOME/.local/share/munassiq-signing"
keytool -genkeypair -keystore "$HOME/.local/share/munassiq-signing/release.jks" -alias munassiq -keyalg RSA -keysize 3072 -validity 10000
```

The first command creates a private folder. The second creates the signing key and
prompts locally for passwords/certificate identity. Do not paste passwords in chat
or put them on command lines. Preserve an existing key instead of regenerating it.

## Build in your terminal

```bash
export MUNASSIQ_KEYSTORE_FILE="$HOME/.local/share/munassiq-signing/release.jks"
export MUNASSIQ_KEY_ALIAS=munassiq
read -rsp 'Keystore password: ' MUNASSIQ_STORE_PASSWORD; echo
read -rsp 'Key password: ' MUNASSIQ_KEY_PASSWORD; echo
export MUNASSIQ_STORE_PASSWORD MUNASSIQ_KEY_PASSWORD
bash operations/scripts/build_android.sh --release --console=plain 2>&1 | tee "$HOME/munassiq-release-build.log"
unset MUNASSIQ_STORE_PASSWORD MUNASSIQ_KEY_PASSWORD
```

These supply signing secrets only to the build process, build the release and
remove the password variables afterwards. The source requires all signing settings
and refuses release with validation=true. No version was changed: the existing
code=1/name=0.1.0 remains until you explicitly choose a version increase. Future
updates need a higher version code and the same signing key.

Expected successful output: android/app/build/outputs/apk/release/app-release.apk.
Do not advertise it until the build succeeds and installation/client checks pass.
A debug validation install uses a different signing key: uninstall that development
copy before the first release install. Subsequent real releases should update in place.

## Verify and publish an existing release

Read the PUBLIC signing-certificate SHA-256 with keytool -list -v -keystore followed
by your key path and -alias munassiq. It prompts locally for the keystore password.
Then substitute the public SHA-256 fingerprint below:

```bash
.venv/bin/python -B operations/scripts/publish_apk.py \
  --apk android/app/build/outputs/apk/release/app-release.apk \
  --public-root /var/www/munassiq \
  --certificate-sha256 YOUR_PUBLIC_SIGNING_CERTIFICATE_SHA256
```

This verifies the signature using the selected installed Build Tools, rejects the
debug key/debuggable/wrong-package APK, pins the expected certificate, then copies
the existing APK atomically to downloads/munassiq.apk and writes release-info.json.
It does not build/sign the APK or modify server settings. Keep that fingerprint
independently rather than trusting an unknown APK's self-reported fingerprint.

After install checks, set the dashboard App settings APK URL to
https://YOUR_STATIC_IP/downloads/munassiq.apk and its version code to the actual
verified code. Native update checking compares this code and opens the browser
for download/install. Android requires allowing installation from that browser's
source; allow it only for the trusted download. Web public event pages use the
same configured APK link. Existing settings default to code 0, hiding updates.

## Deep links and verified App Links

IP/self-signed hosting uses the existing HTTPS app/browser chooser and munassiq
scheme. Do not claim verified automatic opening for this setup. The app handles
both event and service HTTPS paths now; a browser still has the public fallback.

For a future owned domain with publicly trusted HTTPS, generate its association:

```bash
.venv/bin/python -B operations/scripts/prepare_app_links.py \
  --sha256 YOUR_PUBLIC_SIGNING_CERTIFICATE_SHA256 \
  --output /var/www/munassiq/.well-known/assetlinks.json
```

The command writes PUBLIC association JSON only and refuses to overwrite an
existing file. Make the file mode 644 and its public parents traversable. The
Nginx configuration serves it as application/json at the exact HTTPS path.
Set server.verify_links=true in Android deployment.properties and rebuild for
that domain. The preparation script rejects enabling this for IP/self-signed or
validation configuration. Android verification and real deep-link behavior still
need device checks; generating JSON alone is not verification.

Primary references:
- https://developer.android.com/studio/publish/app-signing
- https://developer.android.com/training/app-links/configure-assetlinks
