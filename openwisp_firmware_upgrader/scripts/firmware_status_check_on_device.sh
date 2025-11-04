source ../../.env
DEVICE_NAME=$1

API_URL="$API_BASE_URL/api/v1/firmware-upgrader/device/firmware-upgrade-status?name=${DEVICE_NAME}"

RESPONSE=$(
    curl -sS -L "$API_URL"
)

echo "Response: $RESPONSE"