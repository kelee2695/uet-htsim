#!/usr/bin/env python3
"""
分析每条流的路径选择行为
输出CSV：记录每条流的每次选路事件，包括跳过和最终选择
"""

import re
import sys
import csv
import os
import argparse
from collections import defaultdict

def parse_logs(result_file):
    """解析日志"""
    skips = []
    selects = []
    
    with open(result_file, 'r') as f:
        for line in f:
            # 跳过日志
            m = re.search(r'([\d.]+)\s+(\S+)\s+Hashx nextEntropy path\s+(\d+)\s+weight=(\d+)', line)
            if m and 'skipping' in line:
                skips.append({
                    'time': float(m.group(1)),
                    'flow': m.group(2),
                    'path': int(m.group(3)),
                    'weight': int(m.group(4))
                })
                continue
            
            # 选择日志
            m = re.search(r'([\d.]+)\s+(\S+)\s+Hashx nextEntropy selected_path\s+(\d+)\s+weight\s+(\d+)', line)
            if m:
                selects.append({
                    'time': float(m.group(1)),
                    'flow': m.group(2),
                    'path': int(m.group(3)),
                    'weight': int(m.group(4))
                })
    
    return skips, selects

def analyze_by_flow(skips, selects):
    """按流分析"""
    # 合并所有事件
    events = defaultdict(list)
    
    for s in skips:
        events[s['flow']].append({
            'time': s['time'],
            'action': 'SKIP',
            'path': s['path'],
            'weight': s['weight']
        })
    
    for s in selects:
        events[s['flow']].append({
            'time': s['time'],
            'action': 'SELECT',
            'path': s['path'],
            'weight': s['weight']
        })
    
    # 每个流按时间排序
    for flow in events:
        events[flow].sort(key=lambda x: x['time'])
    
    return events

def generate_csv(events, output_file):
    """生成CSV"""
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['flow_name', 'event_no', 'time_us', 'action', 'path_id', 'weight'])
        
        for flow in sorted(events.keys()):
            for i, e in enumerate(events[flow], 1):
                writer.writerow([
                    flow,
                    i,
                    f"{e['time']:.3f}",
                    e['action'],
                    e['path'],
                    e['weight']
                ])

def generate_summary(events, output_file):
    """生成汇总CSV"""
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['flow_name', 'total_events', 'skip_count', 'select_count', 
                        'unique_paths', 'avg_weight_selected'])
        
        for flow in sorted(events.keys()):
            evs = events[flow]
            skips = [e for e in evs if e['action'] == 'SKIP']
            selects = [e for e in evs if e['action'] == 'SELECT']
            
            unique_paths = len(set(e['path'] for e in evs))
            avg_weight = sum(e['weight'] for e in selects) / len(selects) if selects else 0
            
            writer.writerow([
                flow,
                len(evs),
                len(skips),
                len(selects),
                unique_paths,
                f"{avg_weight:.2f}"
            ])

def main():
    parser = argparse.ArgumentParser(description='分析路径选择行为')
    parser.add_argument('result_file', help='结果文件路径')
    parser.add_argument('-o', '--output', help='输出目录（默认：脚本所在目录）')
    args = parser.parse_args()
    
    result_file = args.result_file
    
    # 确定输出目录
    if args.output:
        output_dir = args.output
        os.makedirs(output_dir, exist_ok=True)
    else:
        # 默认使用脚本所在目录
        output_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 生成输出文件名
    base_name = os.path.splitext(os.path.basename(result_file))[0]
    detail_file = os.path.join(output_dir, f"{base_name}_path_detail.csv")
    summary_file = os.path.join(output_dir, f"{base_name}_path_summary.csv")
    
    # 解析日志
    skips, selects = parse_logs(result_file)
    events = analyze_by_flow(skips, selects)
    
    # 生成CSV
    generate_csv(events, detail_file)
    generate_summary(events, summary_file)
    
    print(f"详细记录: {detail_file}")
    print(f"汇总统计: {summary_file}")
    print(f"\n共分析 {len(events)} 条流")
    print(f"总跳过次数: {len(skips)}")
    print(f"总选择次数: {len(selects)}")

if __name__ == '__main__':
    main()
