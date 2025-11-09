#!/usr/bin/env python3
"""
Simple 4G PCI Lock Test - Access by Key
"""

import json
import argparse
import sys


def parse_config(config_str):
    """Parse CONFIGURATION string to JSON"""
    
    # Remove 'CONFIGURATION=' if present
    if 'CONFIGURATION=' in config_str:
        config_str = config_str.split('CONFIGURATION=')[1]
    
    # Remove spaces and { }
    config_str = config_str.strip().strip('{}')
    
    # Build JSON string
    pairs = []
    items = config_str.split(',')
    
    item_count = len(items)
    index = 0
    
    while index < item_count:
        item = items[index]
        if ':' in item:
            key, value = item.split(':', 1)
            key = key.strip()
            value = value.strip()
            pairs.append(f'"{key}":"{value}"')
        index += 1
    
    json_str = '{' + ','.join(pairs) + '}'
    config = json.loads(json_str)
    
    return config


# Main execution
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='4G PCI Lock Test')
    parser.add_argument('config', help='Configuration string')
    
    args = parser.parse_args()
    
    # Parse configuration
    config = parse_config(args.config)
    
    # Access by key and print
    bandwidth = config.get('bandwidth', 'Not provided')
    lock = config.get('lock', 'Not provided')
    
    print(f"bandwidth : {bandwidth}")
