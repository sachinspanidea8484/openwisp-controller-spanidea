source ../../.env
API_URL="$API_BASE_URL/api/v1/firmware-upgrader/firmware/upgrade/"
FIRMWARE_IMAGE=$1
FIRMWARE_IMAGE_TYPE=$2
DEVICE_NAME=$3
VERSION=$4
OS=$5
PAYLOAD=$(cat <<EOF
{
  "category": {},
  "build": {
    "version": "$VERSION",
    "os": "$OS",
    "changelog": ""
  },
  "device_name": "$DEVICE_NAME",
  "upgrade_options": {
    "c": false
  },
  "firmware_image_type": "$FIRMWARE_IMAGE_TYPE",
  "firmware_image": "$FIRMWARE_IMAGE"
}
EOF
)

if [[ "$FIRMWARE_IMAGE" =~ ^https?:// ]]; then
  # hosted link → don't upload file
  RESPONSE=$(
    curl -s -X POST "$API_URL" \
         -F "firmware_details=$PAYLOAD"
  )
else
  # local file → upload the file
  RESPONSE=$(
    curl -s -X POST "$API_URL" \
         -F "firmware_details=$PAYLOAD" \
         -F "firmware_image=@$FIRMWARE_IMAGE"
  )
fi

echo "api response : $RESPONSE"

