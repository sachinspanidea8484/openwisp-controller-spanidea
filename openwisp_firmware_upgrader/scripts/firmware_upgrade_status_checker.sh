#!/bin/bash

################################################################################
# Firmware Upgrade Status Checker
# Usage: ./firmware_upgrade_status_checker.sh --device <device_name> [--json]
################################################################################

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../.env"

# Configuration
API_BASE_URL="${API_BASE_URL:-http://172.17.0.1:8000}"
API_ENDPOINT="/api/v1/firmware-upgrader/device/firmware-upgrade-status"

# Default values
DEVICE_NAME=""
JSON_OUTPUT=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --device) DEVICE_NAME="$2"; shift 2 ;;
        --json) JSON_OUTPUT=true; shift ;;
        -h|--help) 
            echo "Usage: $(basename "$0") --device <name> [--json]"
            exit 0 
            ;;
        *) echo "Error: Unknown option $1"; exit 1 ;;
    esac
done

# Validate required arguments
[[ -z "$DEVICE_NAME" ]] && { echo "Error: --device is required"; exit 1; }

# Build API URL
API_URL="${API_BASE_URL}${API_ENDPOINT}?name=${DEVICE_NAME}"

# Make API request
[[ "$JSON_OUTPUT" == false ]] && echo "Checking status for device: $DEVICE_NAME"

HTTP_RESPONSE=$(curl -sS -w "\nHTTP_STATUS:%{http_code}" -L "$API_URL" 2>&1) || {
    echo "Error: Failed to connect to API"
    exit 1
}

# Parse response
HTTP_BODY=$(echo "$HTTP_RESPONSE" | sed -e 's/HTTP_STATUS\:.*//g')
HTTP_STATUS=$(echo "$HTTP_RESPONSE" | tr -d '\n' | sed -e 's/.*HTTP_STATUS://')

# Display results
if [[ "$JSON_OUTPUT" == true ]]; then
    echo "$HTTP_BODY"
else
    echo "Status: $HTTP_STATUS"
    echo "$HTTP_BODY" | python3 -m json.tool 2>/dev/null || echo "$HTTP_BODY"
fi

# Exit with status code
[[ "$HTTP_STATUS" -ge 200 && "$HTTP_STATUS" -lt 300 ]] && exit 0 || exit 1