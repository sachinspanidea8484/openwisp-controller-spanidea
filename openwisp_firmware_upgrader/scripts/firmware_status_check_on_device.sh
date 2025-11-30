source ../../.env
DEVICE_NAME=$1

API_URL="http://172.17.0.1:8000/api/v1/firmware-upgrader/device/firmware-upgrade-status?name=${DEVICE_NAME}"

RESPONSE=$(
    curl -sS -L "$API_URL"
)

echo "Response: $RESPONSE"