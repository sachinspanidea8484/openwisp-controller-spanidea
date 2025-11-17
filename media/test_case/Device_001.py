#!/usr/bin/env python3
"""
Simple 4G PCI Lock Test - Access by Key
"""

import json
import argparse
import sys


def parse_config(config_str):
    """Parse CONFIGURATION=... style string into a Python dict"""

    # Remove 'CONFIGURATION=' prefix if present
    if config_str.startswith("CONFIGURATION="):
        config_str = config_str[len("CONFIGURATION="):]

    # Try to parse the remaining string as JSON
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing CONFIGURATION JSON: {e}", file=sys.stderr)
        return {}


# Main execution
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='4G PCI Lock Test')
    parser.add_argument('config', help='Configuration string')

    args = parser.parse_args()

    # Parse configuration
    config = parse_config(args.config)

    # Access by key and print
    RPI = config.get('RPI', config.get('RPIS', 'Not provided'))

    print(f"RPI : {RPI}")