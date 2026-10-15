#!/usr/bin/env bash
# Run manually by the user. Select exact tools for this command only.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
android_tools_root="${MUNASSIQ_ANDROID_TOOLS_ROOT:-/opt/android-shared}"
android_sdk="$android_tools_root/Sdk"
android_gradle="$android_tools_root/gradle/gradle-8.13/bin/gradle"
if [[ ! -x "$android_gradle" || ! -f "$android_sdk/platforms/android-35/android.jar" || ! -x "$android_sdk/build-tools/35.0.0/aapt2" ]]; then
  echo 'Required side-by-side tools are missing. Run setup_android_tools.py first.' >&2
  exit 1
fi
if [[ "${1:-}" == '--validation' ]]; then
  shift
  validation_config="$(mktemp /tmp/munassiq-validation-XXXXXX.properties)"
  trap 'rm -f "$validation_config"' EXIT
  # Reserved documentation address; validation builds block API connections.
  printf '%s\n' 'server.origin=https://192.0.2.1' > "$validation_config"
  python3 -B "$project_dir/operations/scripts/prepare_android.py" --config "$validation_config" --validation
else
  if [[ ! -f "$project_dir/android/deployment.properties" ]]; then
    echo 'Configure android/deployment.properties, or explicitly use --validation for a non-connecting APK.' >&2
    exit 1
  fi
  python3 -B "$project_dir/operations/scripts/prepare_android.py"
fi
# These environment values apply only to Gradle and its child processes.
env ANDROID_HOME="$android_sdk" ANDROID_SDK_ROOT="$android_sdk" \
  "$android_gradle" --project-dir "$project_dir/android" :app:assembleDebug "$@"
