source ../../.env
API_URL="$API_BASE_URL/api/v1/firmware-upgrader/firmware/upgrade/"
FIRMWARE_IMAGE=$1
DEVICE_NAME=$2
PAYLOAD=$(cat <<EOF
{
  "category": {},
  "build": {
    "version": "v2.1.6",
    "os": "openwrt-23.13",
    "changelog": "Bug fixes and WiFi improvements v5"
  },
  "device_name": "$DEVICE_NAME",
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

