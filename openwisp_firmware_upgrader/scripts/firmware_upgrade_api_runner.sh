source ../../.env
API_URL="$API_BASE_URL/api/v1/firmware-upgrader/firmware/upgrade/"
FIRMWARE_IMAGE=$1
PAYLOAD=$(cat <<EOF
{
  "category": {},
  "build": {
    "version": "v2.1.4",
    "os": "openwrt-23.12",
    "changelog": "Bug fixes and WiFi improvements v5"
  },
  "device_id": "b7d6adb3-f87f-4331-a194-0fcd04f9e8d8",
  "upgrade_options": {
    "c": false
  },
  "firmware_image_type": "24.10-openwrt-x86-64-generic-ext4-combined.img-openwisp-python3-http.gz",
  "firmware_image": "$FIRMWARE_IMAGE"
}
EOF
)

RESPONSE=$(
    curl -s -X POST "$API_URL" \
    -F "firmware_details=$PAYLOAD" \
    
)

echo "api response : $RESPONSE"

