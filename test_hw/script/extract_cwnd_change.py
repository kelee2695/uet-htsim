#!/usr/bin/env python3
import sys
import argparse
import csv
import re

def extract_cwnd_data(input_file, map_file, output_file):
    try:
        with open(map_file, 'r') as mapfile:
            reader = csv.DictReader(mapfile)
            flowid_to_uec = {}
            for row in reader:
                flowid_to_uec[row['flowid']] = row['flow_name']
        
        with open(input_file, 'r') as infile:
            lines = infile.readlines()
        
        cwnd_data = {}
        
        for line in lines:
            if 'processAck:' in line and 'cwnd' in line:
                match = re.search(r'At ([\d.]+) (Uec_\d+_\d+).*cwnd (\d+)', line)
                if match:
                    time = match.group(1)
                    flow_name = match.group(2)
                    cwnd = match.group(3)
                    
                    if flow_name not in cwnd_data:
                        cwnd_data[flow_name] = []
                    cwnd_data[flow_name].append((float(time), cwnd))
        
        with open(output_file, 'w') as outfile:
            outfile.write("time,flow,cwnd\n")
            for flow_name in sorted(cwnd_data.keys()):
                for time, cwnd in cwnd_data[flow_name]:
                    outfile.write(f"{time},{flow_name},{cwnd}\n")
        
        total_points = sum(len(data) for data in cwnd_data.values())
        print(f"Processed {len(lines)} lines from {input_file}")
        print(f"Loaded {len(flowid_to_uec)} flow mappings from {map_file}")
        print(f"Found {len(cwnd_data)} flows with {total_points} cwnd data points")
        print(f"Wrote cwnd data to {output_file}")
    
    except FileNotFoundError as e:
        print(f"Error: Input file '{e.filename}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract processAck cwnd data for plotting')
    parser.add_argument('-i', '--input', required=True, help='Input file path')
    parser.add_argument('-m', '--map', required=True, help='Flow mapping CSV file path')
    parser.add_argument('-o', '--output', required=True, help='Output file path')
    
    args = parser.parse_args()
    
    extract_cwnd_data(args.input, args.map, args.output)
