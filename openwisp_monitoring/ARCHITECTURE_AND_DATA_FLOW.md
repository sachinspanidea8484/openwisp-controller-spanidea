# OpenWISP Monitoring - Architecture and Data Flow Documentation

## Table of Contents
1. [Overview](#overview)
2. [Architecture Components](#architecture-components)
3. [Data Collection Process](#data-collection-process)
4. [Temporary Storage System](#temporary-storage-system)
5. [Data Transmission to Controller](#data-transmission-to-controller)
6. [Adding New Statistics](#adding-new-statistics)
7. [Configuration](#configuration)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The OpenWISP Monitoring system for OpenWrt uses a **dual-process architecture** to collect device metrics and send them to the OpenWISP Controller. The system ensures reliable data delivery even with intermittent connectivity through a local temporary storage mechanism.

### Key Design Principles
- **Separation of concerns**: Data collection and transmission are separate processes
- **Fault tolerance**: Temporary storage prevents data loss during connectivity issues
- **Memory awareness**: Automatic management of storage based on available memory
- **Retry mechanism**: Automatic retries with exponential backoff
- **Compression**: Data is gzip-compressed to save bandwidth and storage

---

## Architecture Components

### 1. Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      OpenWrt Device                              │
│                                                                   │
│  ┌──────────────────┐          ┌──────────────────┐             │
│  │ Collect Process  │          │  Send Process     │             │
│  │  (monitoring)    │          │  (monitoring)     │             │
│  └────────┬─────────┘          └────────┬─────────┘             │
│           │                              │                        │
│           │ Calls every interval         │ Reads files           │
│           ▼                              ▼                        │
│  ┌──────────────────┐          ┌──────────────────┐             │
│  │netjson-monitoring│          │  /tmp/openwisp/  │             │
│  │     .lua         │──Writes─▶│   monitoring/    │             │
│  │ (data collector) │          │  [timestamped    │             │
│  └──────────────────┘          │   .gz files]     │             │
│                                 └──────────────────┘             │
│                                         │                         │
│                                         │ HTTP POST              │
│                                         ▼                         │
│                                   ┌──────────┐                   │
│                                   │   curl   │                   │
│                                   └─────┬────┘                   │
└─────────────────────────────────────────┼────────────────────────┘
                                          │
                                          │ HTTPS
                                          ▼
                            ┌──────────────────────────┐
                            │  OpenWISP Controller     │
                            │  /api/v1/monitoring/     │
                            │  device/{uuid}/          │
                            └──────────────────────────┘
```

### 2. File Structure

```
/usr/sbin/
├── openwisp-monitoring         # Main agent script (monitoring.agent)
└── netjson-monitoring          # CLI wrapper (netjson-monitoring shell script)

/usr/libexec/
└── netjson-monitoring          # Actual Lua collector (netjson-monitoring.lua)

/usr/lib/lua/openwisp-monitoring/
├── dhcp.lua                    # DHCP leases collection
├── interfaces.lua              # Network interfaces data
├── monitoring.lua              # Main module orchestrator
├── neighbors.lua               # ARP/neighbor table
├── resources.lua               # CPU, memory, disk usage
├── routes.lua                  # IP routing tables (NEW)
├── utils.lua                   # Utility functions
├── wifi.lua                    # WiFi statistics
└── iwinfo.lua                  # WiFi hardware info (optional)

/etc/init.d/
└── openwisp-monitoring         # Init script (monitoring.init)

/etc/config/
└── openwisp-monitoring         # Configuration file

/etc/hotplug.d/openwisp/
└── openwisp-monitoring         # Hotplug handler

/tmp/openwisp/monitoring/       # Temporary data storage (RUNTIME)
├── 04-11-2025_12:00:00.gz     # Compressed monitoring data
├── 04-11-2025_12:05:00.gz     # Timestamped files
└── response.txt                # HTTP response cache
```

---

## Data Collection Process

### Step-by-Step Collection Flow

#### 1. **Service Initialization** (`monitoring.init`)
```bash
/etc/init.d/openwisp-monitoring start
```

The init script starts **two separate processes**:

**Process 1: Data Collector**
```bash
/usr/sbin/openwisp-monitoring \
    --interval 300 \
    --verbose_mode 0 \
    --required_memory 0.05 \
    --mode collect \
    --monitored_interfaces "*"
```

**Process 2: Data Sender**
```bash
/usr/sbin/openwisp-monitoring \
    --url https://controller.example.com \
    --uuid <device-uuid> \
    --key <device-key> \
    --interval 300 \
    --mode send
```

#### 2. **Collection Cycle** (`monitoring.agent` - `save_data()`)

Every `INTERVAL` seconds (default: 300s = 5 minutes):

1. **Check available memory**
   - **File:** `monitoring.agent`
   - **Function:** `check_available_memory()` (lines 39-62)
   - **What it does:**
     - Queries system memory via ubus: `ubus call system info`
     - Calculates required memory: `required = total * 0.05` (5% by default)
     - If insufficient, deletes oldest data file
     - If no files exist and memory is low, skips collection
   ```bash
   check_available_memory() {
       total=$(ubus call system info | jsonfilter -e '@.memory.total')
       available=$(ubus call system info | jsonfilter -e '@.memory.available')
       required=$(echo - | awk -v percent="$REQUIRED_PERCENT" -v total="$total" '{printf("%.f",percent*total)}')
       # Deletes old files if memory is insufficient
   }
   ```
   
2. **Collect monitoring data**
   - **File:** `monitoring.agent`
   - **Function:** `collect_data()` (lines 64-77)
   - **What it does:**
     - Calls the netjson-monitoring script with retry logic (up to 5 attempts)
     - Returns collected JSON data
   ```bash
   collect_data() {
       /usr/sbin/netjson-monitoring --dump "$MONITORED_INTERFACES"
   }
   ```
   This executes:
   ```bash
   /usr/libexec/netjson-monitoring "*"
   ```
   Which is the Lua script (`netjson-monitoring.lua`) that collects all metrics

3. **Generate timestamp filename**
   - **File:** `monitoring.agent`
   - **Function:** `save_data()` (line 103)
   - **What it does:**
     - Creates UTC timestamp for filename
   ```bash
   filename=$(date -u +'%d-%m-%Y_%H:%M:%S')
   # Example: 04-11-2025_12:05:00
   ```

4. **Save to temporary file**
   - **File:** `monitoring.agent`
   - **Function:** `save_data()` (line 105)
   - **What it does:**
     - Writes collected data to temporary file with timestamp name
   ```bash
   echo "$data" > "/tmp/openwisp/monitoring/$filename"
   ```

5. **Compress the file**
   - **File:** `monitoring.agent`
   - **Function:** `save_data()` (line 107)
   - **What it does:**
     - Compresses the JSON file using gzip to save space and bandwidth
   ```bash
   gzip "/tmp/openwisp/monitoring/$filename"
   # Creates: /tmp/openwisp/monitoring/04-11-2025_12:05:00.gz
   ```

6. **Signal the sender process**
   - **File:** `monitoring.agent`
   - **Function:** `save_data()` (lines 112-113)
   - **What it does:**
     - Finds the send process PID and signals it to start sending
     - Uses SIGUSR1 signal to wake up the sender without interrupting it
   ```bash
   pid=$(pgrep -f "openwisp-monitoring.*--mode send")
   kill -SIGUSR1 "$pid"
   ```

#### 3. **NetJSON Data Collection** (`netjson-monitoring.lua`)

The Lua script collects data from various sources:

```lua
-- System information (via ubus)
ubus:call('system', 'info', {})
ubus:call('system', 'board', {})

-- Network devices
ubus:call('network.device', 'status', {})
ubus:call('network.wireless', 'status', {})

-- Monitoring modules
monitoring.resources.get_cpus()
monitoring.resources.parse_disk_usage()
monitoring.dhcp.get_dhcp_leases()
monitoring.neighbors.get_neighbors()
monitoring.routes.get_routes()           # NEW
monitoring.interfaces.get_addresses()
monitoring.wifi.netjson_clients()
```

**Output Format**: NetJSON DeviceMonitoring
```json
{
  "type": "DeviceMonitoring",
  "general": {
    "hostname": "OpenWrt",
    "local_time": 1699012345,
    "uptime": 86400
  },
  "resources": {
    "load": [0.5, 0.3, 0.2],
    "memory": { "total": 512000, "free": 256000 },
    "cpus": 2,
    "disk": [...]
  },
  "dhcp_leases": [...],
  "neighbors": [...],
  "routes": {                    # NEW
    "ipv4": [...],
    "ipv6": [...]
  },
  "interfaces": [...]
}
```

---

## Temporary Storage System

### Storage Location
```
/tmp/openwisp/monitoring/
```
**Why `/tmp`?**
- OpenWrt typically uses RAM-based tmpfs for `/tmp`
- Fast read/write operations
- Automatically cleared on reboot (prevents stale data accumulation)
- No wear on flash storage

### File Naming Convention
```
DD-MM-YYYY_HH:MM:SS.gz
```
Example: `04-11-2025_12:05:00.gz`

**Purpose of timestamp naming:**
- Files are naturally sorted chronologically
- Controller can use timestamp in API query: `?time=04-11-2025_12:05:00.000000`
- Enables proper time-series data storage
- Helps identify data collection period

### Memory Management

The system implements **automatic memory-aware cleanup**:

1. **Before collecting data**, check if enough memory is available
2. **Required memory** = `total_memory * required_percent` (default 5%)
3. **If insufficient memory**:
   - Delete **oldest** file first (using `ls -1t | tail -1`)
   - Repeat until enough memory is available
   - If no files to delete, skip this collection cycle

### File Lifecycle

```
Collection → Compression → Storage → Transmission → Deletion
    ↓            ↓            ↓            ↓            ↓
[JSON data] → [.gz file] → [/tmp/...] → [HTTP POST] → [rm file]
                                 ↓
                          [If send fails: kept for retry]
```

---

## Data Transmission to Controller

### Transmission Process (`monitoring.agent` - `send_data()`)

#### 1. **Wait for Device Registration**
- **File:** `monitoring.agent`
- **Function:** `wait_until_registered()` (lines 235-251)
- **What it does:**
  - Waits for `UUID` and `KEY` from `/etc/config/openwisp`
  - These are set by `openwisp-config` agent during device registration
  - Checks every `REGISTRATION_INTERVAL` (interval/10) seconds
```bash
wait_until_registered() {
    UUID=$(uci get openwisp.http.uuid 2>/dev/null)
    KEY=$(uci get openwisp.http.key 2>/dev/null)
    # Returns 0 when both are available
}
```

#### 2. **File Processing Loop**

**File:** `monitoring.agent`  
**Function:** `send_data()` (lines 124-233)  
**Main Loop:** Lines 126-232

For each file in `/tmp/openwisp/monitoring/`:

1. **Skip special files**
   - **Location:** Line 141
   - **What it does:**
     - Ignores `response.txt` (used for storing HTTP responses)
     - Skips non-existent files
   ```bash
   [ "$filename" = "response" ] && rm "$file" 2>/dev/null && continue
   ```

2. **Decompress if needed**
   - **Location:** Lines 148-151
   - **What it does:**
     - Checks if file has .gz extension
     - Decompresses before reading
   ```bash
   if [ "${basefilename##*.}" = "gz" ]; then
       gzip -d "$file"
   fi
   ```

3. **Build API URL**
   - **Location:** Lines 143-147
   - **What it does:**
     - Constructs the full API endpoint with authentication
     - Adds timestamp from filename
     - Marks as current if it's the only/latest file
   ```bash
   url="$URL&time=$filename.000000"
   [ "$(echo "$TMP_DIR"/* | awk '{print $2}')" ] || url="$url&current=true"
   ```
   
   **Query parameters:**
   - `key`: Device authentication key
   - `time`: Timestamp from filename (with microsecond precision: `.000000`)
   - `current=true`: Added if this is the latest/only file

4. **Send data via curl**
   - **Location:** Line 179
   - **Function:** Uses `$CURL_COMMAND` set by `set_url_and_curl()` (lines 79-97)
   - **What it does:**
     - POSTs JSON data to controller
     - Captures HTTP status code
     - Saves response to file
   ```bash
   response_code=$($CURL_COMMAND -H "Content-Type: application/json" -d "$data" "$url")
   ```
   
   The curl command is built with:
   ```bash
   CURL_COMMAND="curl -s -w "%{http_code}" --output $RESPONSE_FILE"
   ```

5. **Handle HTTP responses**
   - **Location:** Lines 180-222
   - **What it does:**
     - Processes HTTP status codes from controller
     - Deletes file on success
     - Retries or discards based on error type

   | HTTP Code | Action | Line | Description |
   |-----------|--------|------|-------------|
   | **200** | Delete file | 180-194 | Data successfully received |
   | **400** | Delete file | 195-200 | Bad request - malformed data, don't retry |
   | **404** | Check if device deleted | 206-219 | Device might be removed from controller |
   | **Other** | Retry with backoff | 201-221 | Network/server issues, retry later |

#### 3. **Retry Mechanism**

- **File:** `monitoring.agent`
- **Function:** `send_data()` (lines 161-222)
- **What it does:**
  - Retries failed transmissions with exponential backoff
  - Gives up after MAX_RETRIES attempts
  - Uses random delays to prevent thundering herd

```bash
MAX_RETRIES=5  # Default, configurable (line 94)
failures=0

while [ "$failures" -lt "$MAX_RETRIES" ]; do
    response_code=$(curl ...)
    
    if [ "$response_code" = "200" ]; then
        rm -f "$filename"  # Delete on success (line 193)
        break
    else
        timeout=$(/usr/sbin/openwisp-get-random-number 2 15)  # Line 202
        sleep "$timeout"
        failures=$((failures + 1))
    fi
done
```

**Exponential backoff strategy:**
- First retry: 2-15 seconds (random)
- Continues up to `MAX_RETRIES` times
- If all retries fail, file is kept for next cycle
- Prevents server overload during outages

#### 4. **Rate Limiting**

- **File:** `monitoring.agent`
- **Function:** `send_data()` (lines 227-230)
- **What it does:**
  - Prevents overwhelming the controller with rapid requests
  - Pauses after successful batches

```bash
if [ $((success % 10)) -eq 0 ]; then
    pause_duration=$(/usr/sbin/openwisp-get-random-number 1 5)  # Line 228
    sleep "$pause_duration"
fi
```
- After every 10 successful transmissions
- Pause for 1-5 seconds (random)
- Prevents overwhelming the controller

### API Endpoint

**URL Structure:**
```
POST https://{controller}/api/v1/monitoring/device/{uuid}/?key={key}&time={timestamp}&current={bool}
```

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "type": "DeviceMonitoring",
  "general": { ... },
  "resources": { ... },
  "interfaces": [ ... ],
  ...
}
```

**Authentication:**
- Device UUID in URL path
- Device key in query parameter
- Both obtained from OpenWISP Config agent

### Error Handling

#### Device Deletion Detection (HTTP 404)
```bash
if [ "$response_code" = "404" ]; then
    if ! pgrep -x "openwisp-config" >/dev/null; then
        # OpenWISP Config agent not running - device likely deleted
        logger -s "Device may have been deleted from OpenWISP Controller"
        kill $(pgrep -f "openwisp-monitoring.*--mode collect")
        exit 2
    fi
fi
```

---

## Adding New Statistics

### Quick Guide: Adding Custom Metrics

When you want to add new monitoring data (like we did with routes), follow this pattern:

#### Step 1: Create a New Module

Create a new Lua file in `files/lib/openwisp-monitoring/`:

```lua
-- files/lib/openwisp-monitoring/your_metric.lua
local io = require('io')
local utils = require('openwisp-monitoring.utils')

local your_metric = {}

function your_metric.collect_data()
    local data = {}
    
    -- Collect your data using:
    -- 1. Shell commands via io.popen()
    local cmd_output = io.popen('your-command'):read('*a')
    
    -- 2. Parse the output
    for line in cmd_output:gmatch("[^\n]+") do
        -- Parse each line
        table.insert(data, parsed_item)
    end
    
    return data
end

return your_metric
```

**Best Practices for Data Collection:**
- Use `io.popen()` for shell commands
- Always close file handles: `file:close()`
- Handle errors gracefully with `pcall()`
- Return empty table `{}` if no data
- Keep functions focused and modular
- Use existing utility functions from `utils.lua`

#### Step 2: Register in Main Module

Edit `files/lib/openwisp-monitoring/monitoring.lua`:

```lua
monitoring.your_metric = require('openwisp-monitoring.your_metric')
```

#### Step 3: Integrate into NetJSON Output

Edit `files/sbin/netjson-monitoring.lua`:

```lua
-- Collect your metric data
local your_data = monitoring.your_metric.collect_data()

-- Add to netjson output if not empty
if not monitoring.utils.is_table_empty(your_data) then
    netjson.your_metric = your_data
end
```

**Where to place it:**
- After system info but before interfaces (if it's device-level data)
- Within interface loop (if it's per-interface data)
- Follow existing pattern for consistency

#### Step 4: Update Makefile (if needed)

If your module is always required, add to `Makefile`:

```makefile
$(INSTALL_DATA) \
    files/lib/openwisp-monitoring/your_metric.lua \
    $(1)/usr/lib/lua/openwisp-monitoring/your_metric.lua
```

If optional, use conditional installation like `iwinfo.lua`.

#### Step 5: Test Your Changes

**Local testing:**
```bash
# Test your module directly
lua -e "
package.path = package.path .. ';./files/lib/?.lua'
local metric = require('openwisp-monitoring.your_metric')
local cjson = require('cjson')
print(cjson.encode(metric.collect_data()))
"

# Test full collection
cd package/openwisp-monitoring
./files/sbin/netjson-monitoring.lua | grep -A 20 your_metric
```

**On OpenWrt device:**
```bash
# Manual test
/usr/sbin/netjson-monitoring --dump "*"

# Check logs
logread | grep openwisp-monitoring

# Verify data file creation
ls -lah /tmp/openwisp/monitoring/

# Check one data file
zcat /tmp/openwisp/monitoring/*.gz | head -100
```

### Real-World Example: Routes Module

Let's walk through how the routes module was added:

**1. Created `routes.lua`:**
```lua
-- Collects IP routing information
function routes.get_routes()
    local all_routes = {ipv4 = {}, ipv6 = {}}
    
    -- Try JSON format first
    local ipv4_routes = routes.get_ip_route_json()
    
    -- Fallback to text parsing
    if next(ipv4_routes) == nil then
        ipv4_routes = routes.parse_ip_route()
    end
    
    -- Collect IPv6
    local ipv6_routes = routes.get_ipv6_routes()
    
    return all_routes
end
```

**2. Registered in `monitoring.lua`:**
```lua
monitoring.routes = require('openwisp-monitoring.routes')
```

**3. Added to `netjson-monitoring.lua`:**
```lua
local routing_table = monitoring.routes.get_routes()
if not monitoring.utils.is_table_empty(routing_table.ipv4) or 
   not monitoring.utils.is_table_empty(routing_table.ipv6) then
    netjson.routes = routing_table
end
```

**4. Data flows automatically:**
- Collected every interval
- Stored in `/tmp/openwisp/monitoring/`
- Sent to controller
- Available in controller API/dashboard

### Data Format Considerations

**For Controller Compatibility:**
1. **Use standard NetJSON types** when possible
2. **Keep structure flat** - avoid deep nesting
3. **Use arrays for lists**, objects for key-value pairs
4. **Include timestamps** if time-series data
5. **Be consistent** with data types (don't mix strings/numbers)

**Example Good Structure:**
```json
{
  "metric_name": [
    {
      "field1": "value",
      "field2": 123,
      "timestamp": 1699012345
    }
  ]
}
```

### Controller-Side Integration

For new metrics to appear in OpenWISP Controller:

1. **Controller must recognize the field** in the NetJSON schema
2. **Database schema** might need updating for persistent storage
3. **API endpoints** should expose the new data
4. **UI dashboards** need to visualize it

**Note:** The OpenWrt agent just collects and sends - controller decides what to do with the data.

---

## Configuration

### Main Configuration File

**Location:** `/etc/config/openwisp-monitoring`

```bash
config monitoring 'monitoring'
    option monitored_interfaces '*'      # Interfaces to monitor (* = all)
    option interval '300'                 # Collection interval in seconds
    option verbose_mode '0'               # Enable verbose logging (0/1)
    option required_memory '0.05'         # Memory threshold (5% of total)
    option max_retries '5'                # Max retries for sending data
    option bootup_delay '10'              # Delay before starting (seconds)
```

### OpenWISP Config Integration

**Location:** `/etc/config/openwisp`

```bash
config http 'http'
    option url 'https://controller.example.com'
    option uuid '12345678-1234-1234-1234-123456789abc'
    option key 'secret-device-key'
    option verify_ssl '1'
    option cacert '/etc/ssl/certs/ca-certificates.crt'
```

### Time Intervals

You can specify intervals in multiple formats:
- Seconds: `300` or `300s`
- Minutes: `5m`
- Hours: `1h`
- Days: `1d`

**Conversion function** (`monitoring.init`):
```bash
time_to_seconds() {
    # Accepts: 300, 300s, 5m, 1h, 1d
    # Returns: seconds
}
```

---

## Troubleshooting

### Check Service Status
```bash
/etc/init.d/openwisp-monitoring status
ps | grep openwisp-monitoring
```

### View Logs
```bash
# Real-time monitoring
logread -f | grep openwisp

# View all monitoring logs
logread | grep openwisp-monitoring
```

### Check Temporary Storage
```bash
# List collected data files
ls -lh /tmp/openwisp/monitoring/

# Count pending files
ls /tmp/openwisp/monitoring/*.gz 2>/dev/null | wc -l

# View a compressed data file
zcat /tmp/openwisp/monitoring/04-11-2025_12:00:00.gz | head -50

# Check total size
du -sh /tmp/openwisp/monitoring/
```

### Manual Data Collection
```bash
# Collect data manually
/usr/sbin/netjson-monitoring --dump "*"

# Pretty-print JSON
/usr/sbin/netjson-monitoring --dump "*" | jsonfilter -p
```

### Test Communication with Controller
```bash
# Get device credentials
UUID=$(uci get openwisp.http.uuid)
KEY=$(uci get openwisp.http.key)
URL=$(uci get openwisp.http.url)

# Test API endpoint
curl -v "$URL/api/v1/monitoring/device/$UUID/?key=$KEY"
```

### Common Issues

#### 1. Data Not Being Collected
**Check:**
```bash
# Is the service running?
/etc/init.d/openwisp-monitoring status

# Are there errors?
logread | grep -i error | grep openwisp

# Test manual collection
/usr/sbin/netjson-monitoring --dump "*"
```

#### 2. Data Not Being Sent
**Check:**
```bash
# Are credentials set?
uci get openwisp.http.uuid
uci get openwisp.http.key

# Are files accumulating?
ls -l /tmp/openwisp/monitoring/

# Check send process
ps | grep "openwisp-monitoring.*send"

# View recent logs
logread | grep "Data.*sent"
```

#### 3. High Memory Usage
```bash
# Check memory
free -m

# Count data files
ls /tmp/openwisp/monitoring/*.gz | wc -l

# Adjust required memory threshold
uci set openwisp-monitoring.monitoring.required_memory='0.10'  # 10%
uci commit
/etc/init.d/openwisp-monitoring restart
```

#### 4. Files Not Being Deleted
**Possible causes:**
- Network connectivity issues
- Controller is down
- Invalid credentials
- HTTP 400 errors (malformed data)

**Solution:**
```bash
# Check last response
cat /tmp/openwisp/monitoring/response.txt

# Enable verbose mode
uci set openwisp-monitoring.monitoring.verbose_mode='1'
uci commit
/etc/init.d/openwisp-monitoring restart

# Watch logs in real-time
logread -f | grep openwisp
```

---

## Summary

### Data Flow Recap

```
Every 5 minutes (default):
1. Collect Process: Gathers metrics → Saves to /tmp/openwisp/monitoring/DD-MM-YYYY_HH:MM:SS.gz
2. Send Process: Reads files → POSTs to controller → Deletes on success
```

### Key Files and Their Roles

| File | Role |
|------|------|
| `monitoring.agent` | Main orchestrator - manages collect & send processes |
| `netjson-monitoring.lua` | Data collector - gathers all metrics |
| `monitoring.init` | Service manager - starts/stops processes |
| `monitoring.lua` | Module registry - imports all collectors |
| `/tmp/openwisp/monitoring/*.gz` | Temporary storage - compressed data files |
| `/etc/config/openwisp-monitoring` | Configuration - intervals, interfaces, etc. |
