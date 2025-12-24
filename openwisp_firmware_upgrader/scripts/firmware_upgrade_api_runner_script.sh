#!/bin/bash

################################################################################
# Firmware Upgrade API Runner
# 
# Description:
#   Submits firmware upgrade requests to the firmware upgrader API.
#   Supports both local firmware images and hosted URLs.
#
# Usage:
#   ./firmware_upgrade_api_runner.sh \
#     --image <path_or_url> \
#     --type <image_type> \
#     --device <device_name> \
#     --version <version> \
#     --os <operating_system>
#
# Example:
#   ./firmware_upgrade_api_runner_script.sh \
#     --baseUrl http://localhost:8000 \
#     --image /path/to/openwrt-x86-64-generic-ext4-combined.img \
#     --type "QEMU Standard PC (i440FX + PIIX, 1996)" \
#     --device GNS321 \
#     --version "v1.0" \
#     --os "QEMU Standard PC (i440FX + PIIX, 1996)"
################################################################################

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../.env"

# # API Configuration
# API_URL="${API_URL:-http://localhost:8000/api/v1/firmware-upgrader/firmware/upgrade/}"

################################################################################
# Display usage information
################################################################################
usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Options:
    --baseUrl <url>    Base URL of firmware upgrade API (required)
    --image <path_or_url>       Path to local firmware image or hosted URL (required)
    --type <image_type>         Firmware image type (required)
    --device <device_name>      Target device name (required)
    --version <version>         Firmware version (required)
    --os <operating_system>     Operating system name (required)
    --keep-config               Keep existing configuration during upgrade (optional)
    -h, --help                  Display this help message

Example:
    $(basename "$0") \\
        --baseUrl http://localhost:8000 \\
        --image /home/user/firmware.img \\
        --type "QEMU Standard PC" \\
        --device GNS321 \\
        --version "v1.0" \\
        --os "OpenWrt"

EOF
    exit 1
}

################################################################################
# Initialize variables
################################################################################
FIRMWARE_IMAGE=""
FIRMWARE_IMAGE_TYPE=""
DEVICE_NAME=""
VERSION=""
OS=""
BASE_URL=""
KEEP_CONFIG=false

################################################################################
# Parse command-line arguments
################################################################################
while [[ $# -gt 0 ]]; do
    case $1 in
        --image)
            FIRMWARE_IMAGE="$2"
            shift 2
            ;;
        --type)
            FIRMWARE_IMAGE_TYPE="$2"
            shift 2
            ;;
        --device)
            DEVICE_NAME="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --os)
            OS="$2"
            shift 2
            ;;
        --baseUrl)
            BASE_URL="$2"
            shift 2
            ;;
        --keep-config)
            KEEP_CONFIG=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Error: Unknown option: $1"
            usage
            ;;
    esac
done

################################################################################
# Validate required arguments
################################################################################
if [[ -z "$FIRMWARE_IMAGE" || -z "$FIRMWARE_IMAGE_TYPE" || -z "$DEVICE_NAME" || -z "$VERSION" || -z "$OS" || -z "$BASE_URL" ]]; then
    echo "Error: Missing required arguments"
    echo ""
    usage
fi

# Validate local file exists (if not a URL)
if [[ ! "$FIRMWARE_IMAGE" =~ ^https?:// ]] && [[ ! -f "$FIRMWARE_IMAGE" ]]; then
    echo "Error: Firmware image file not found: $FIRMWARE_IMAGE"
    exit 1
fi

# API Configuration
API_URL="${API_URL:-${BASE_URL}/api/v1/firmware-upgrader/firmware/upgrade/}"

################################################################################
# Build JSON payload
################################################################################
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
    "c": $KEEP_CONFIG
  },
  "firmware_image_type": "$FIRMWARE_IMAGE_TYPE",
  "firmware_image": "$FIRMWARE_IMAGE"
}
EOF
)

################################################################################
# Send API request
################################################################################
echo "=========================================="
echo "Firmware Upgrade Request"
echo "=========================================="
echo "API URL: $API_URL"
echo "Device: $DEVICE_NAME"
echo "Version: $VERSION"
echo "OS: $OS"
echo "Image Type: $FIRMWARE_IMAGE_TYPE"
echo "Firmware Image: $FIRMWARE_IMAGE"
echo "Keep Config: $KEEP_CONFIG"
echo "=========================================="
echo ""

# Determine if firmware image is a URL or local file
if [[ "$FIRMWARE_IMAGE" =~ ^https?:// ]]; then
    echo "📡 Sending request with hosted firmware URL..."
    RESPONSE=$(
        curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$API_URL" \
             -H "Content-Type: multipart/form-data" \
             -F "firmware_details=$PAYLOAD"
    )
else
    echo "📤 Uploading local firmware image..."
    RESPONSE=$(
        curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$API_URL" \
             -H "Content-Type: multipart/form-data" \
             -F "firmware_details=$PAYLOAD" \
             -F "firmware_image=@$FIRMWARE_IMAGE"
    )
fi

################################################################################
# Parse and display response
################################################################################
HTTP_BODY=$(echo "$RESPONSE" | sed -e 's/HTTP_STATUS\:.*//g')
HTTP_STATUS=$(echo "$RESPONSE" | tr -d '\n' | sed -e 's/.*HTTP_STATUS://')

echo ""
echo "=========================================="
echo "API Response"
echo "=========================================="
echo "HTTP Status: $HTTP_STATUS"
echo "Response Body:"
echo "$HTTP_BODY" | python3 -m json.tool 2>/dev/null || echo "$HTTP_BODY"
echo "=========================================="

# Exit with appropriate status code
if [[ "$HTTP_STATUS" -ge 200 && "$HTTP_STATUS" -lt 300 ]]; then
    echo "✅ Firmware upgrade request successful"
    exit 0
else
    echo "❌ Firmware upgrade request failed"
    exit 1
fi