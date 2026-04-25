#!/usr/bin/env bash
# Update the Twilio phone number's voice webhook to a new public base URL.
#
# Usage:
#   scripts/update-ngrok.sh                       # auto-detect from local ngrok
#   scripts/update-ngrok.sh https://abcd.ngrok.io # explicit base URL
#
# Reads from .env: TWILIO_ACCOUNT_SID, TWILIO_API_KEY_SID,
# TWILIO_API_KEY_SECRET, TWILIO_PHONE_NUMBER.

set -euo pipefail

WEBHOOK_PATH="/twilio/voice"
ENV_FILE="${ENV_FILE:-.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "error: $ENV_FILE not found (run from repo root or set ENV_FILE)" >&2
  exit 1
fi

# Parse .env safely. We don't `source` because that breaks on:
#   - CRLF line endings (Windows editors)
#   - unquoted values with spaces (e.g. COMPANY_NAME=Acme Insurance)
# We accept KEY=VAL where VAL is the rest of the line, with optional
# surrounding single/double quotes stripped.
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  [[ -z "${line//[[:space:]]/}" ]] && continue
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=(.*)$ ]] || continue
  key="${BASH_REMATCH[1]}"
  val="${BASH_REMATCH[2]}"
  if [[ "$val" =~ ^\"(.*)\"$ ]] || [[ "$val" =~ ^\'(.*)\'$ ]]; then
    val="${BASH_REMATCH[1]}"
  fi
  export "$key=$val"
done < "$ENV_FILE"

for var in TWILIO_ACCOUNT_SID TWILIO_API_KEY_SID TWILIO_API_KEY_SECRET TWILIO_PHONE_NUMBER; do
  if [[ -z "${!var:-}" ]]; then
    echo "error: $var is not set in $ENV_FILE" >&2
    exit 1
  fi
done

for cmd in curl jq; do
  if ! command -v "$cmd" >/dev/null; then
    echo "error: $cmd is required" >&2
    exit 1
  fi
done

if [[ $# -ge 1 ]]; then
  BASE_URL="$1"
else
  # Probe ngrok's local API (default :4040). Try a few hosts so this works
  # whether ngrok runs in this WSL, on the Windows host, or you set
  # NGROK_API to a custom URL.
  candidates=()
  [[ -n "${NGROK_API:-}" ]] && candidates+=("$NGROK_API")
  candidates+=("http://localhost:4040")
  # WSL2 → Windows host: the default gateway points at the Windows side.
  if gw="$(ip route show default 2>/dev/null | awk '/default/ {print $3; exit}')" \
       && [[ -n "$gw" ]]; then
    candidates+=("http://${gw}:4040")
  fi

  BASE_URL=""
  for api in "${candidates[@]}"; do
    if resp="$(curl -fsS --max-time 2 "${api}/api/tunnels" 2>/dev/null)"; then
      BASE_URL="$(jq -r '.tunnels[] | select(.proto=="https") | .public_url' \
                  <<<"$resp" | head -n1)"
      [[ -n "$BASE_URL" ]] && { echo "auto-detected via ${api}"; break; }
    fi
  done

  if [[ -z "$BASE_URL" ]]; then
    echo "error: could not auto-detect ngrok URL on any of: ${candidates[*]}" >&2
    echo "       pass the URL as an argument, or set NGROK_API=http://host:4040" >&2
    exit 1
  fi
fi

VOICE_URL="${BASE_URL%/}${WEBHOOK_PATH}"
AUTH="${TWILIO_API_KEY_SID}:${TWILIO_API_KEY_SECRET}"
API="https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}"

PN_SID="$(curl -fsS -u "$AUTH" \
  --data-urlencode "PhoneNumber=${TWILIO_PHONE_NUMBER}" \
  -G "${API}/IncomingPhoneNumbers.json" \
  | jq -r '.incoming_phone_numbers[0].sid // empty')"

if [[ -z "$PN_SID" ]]; then
  echo "error: no phone number matching ${TWILIO_PHONE_NUMBER} on this account" >&2
  exit 1
fi

curl -fsS -u "$AUTH" -X POST \
  --data-urlencode "VoiceUrl=${VOICE_URL}" \
  --data-urlencode "VoiceMethod=POST" \
  "${API}/IncomingPhoneNumbers/${PN_SID}.json" \
  | jq -r '"updated " + .phone_number + " voice_url -> " + .voice_url'

echo "reminder: also update PUBLIC_BASE_URL=${BASE_URL} in ${ENV_FILE} if your app reads it"
