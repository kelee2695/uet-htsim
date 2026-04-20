#!/usr/bin/env python3
"""
分析 pathid 的分布情况
"""

import argparse
import re
import os
from collections import Counter

def analyze_pathid(filename):
    # 提取 pathid 和 selected_port
    pattern = r'\[HASHX DEBUG\].*pathid=(\d+).*selected_port=(\d+)'
    
    port_counter = Counter()  # 统计每个端口的选中次数
    port_pathids = {5: [], 10: []}  # 特别关注端口 5 和 10
    
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            match = re.search(pattern, line)
            if match:
                pathid = int(match.group(1))
                port = int(match.group(2))
                
                port_counter[port] += 1
                
                if port in port_pathids:
                    port_pathids[port].append(pathid)
    
    print("Selected Port 的分布:")
    for i in sorted(port_counter.keys()):
        count = port_counter[i]
        bar = '#' * (count // 500)
        print(f"  Port {i:2d}: {count:6d} {bar}")
    
    print(f"\n端口 5 的选中次数: {port_counter[5]}")
    print(f"端口 10 的选中次数: {port_counter[10]}")
    
    # 检查哪些端口没有被选中
    all_ports = set(range(32))
    used_ports = set(port_counter.keys())
    unused_ports = sorted(all_ports - used_ports)
    print(f"\n从未被选中的端口: {unused_ports}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True)
    args = parser.parse_args()
    
    analyze_pathid(args.input)

if __name__ == '__main__':
    main()