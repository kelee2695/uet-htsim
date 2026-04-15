#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证 UecMpHashx::processEv 函数中 ECN 权重计算逻辑的正确性

根据代码逻辑：
- ecn_tag = 3: 不做任何操作，直接返回
- ecn_tag = 1: 根据队列大小计算权重
  - queue_low <= ecn_low: weight = 8 (满权重)
  - queue_low >= ecn_high: weight = 0 (零权重)
  - 否则: weight = 8 * (ecn_high - queue_low) / (ecn_high - ecn_low)
"""

import re
import sys
import csv


def calculate_expected_weight(queue_low, ecn_low, ecn_high):
    """
    根据代码逻辑计算期望的权重值
    """
    if ecn_high <= ecn_low:
        return 8  # 无效的阈值，使用默认值
    
    if queue_low <= ecn_low:
        return 8  # 队列低于低阈值，满权重
    elif queue_low >= ecn_high:
        return 0  # 队列高于高阈值，零权重
    else:
        # 线性插值: weight = 8 * (ecn_high - queue_low) / (ecn_high - ecn_low)
        numerator = 8 * (ecn_high - queue_low)
        denominator = ecn_high - ecn_low
        weight = int(numerator / denominator)
        return max(0, min(8, weight))  # 限制在 0-8 范围内


def parse_processEv_logs(result_file):
    """
    解析结果文件中的 Hashx processEvECN 日志
    格式: 2.36728 Uec_31_255 Hashx processEvECN path_id 0 ecn_tag=1, queue_low=128650 ecn_low=91300 ecn_high=361050 new_weight=6
    """
    pattern = r'([\d.]+)\s+(\S+)\s+Hashx processEvECN path_id\s+(\d+)\s+ecn_tag=(\d+),\s+queue_low=(\d+)\s+ecn_low=(\d+)\s+ecn_high=(\d+)\s+new_weight=(\d+)'
    
    logs = []
    with open(result_file, 'r') as f:
        for line in f:
            match = re.search(pattern, line)
            if match:
                logs.append({
                    'time': float(match.group(1)),
                    'flow_name': match.group(2),
                    'path_id': int(match.group(3)),
                    'ecn_tag': int(match.group(4)),
                    'queue_low': int(match.group(5)),
                    'ecn_low': int(match.group(6)),
                    'ecn_high': int(match.group(7)),
                    'actual_weight': int(match.group(8))
                })
    
    return logs


def verify_weights(logs):
    """
    验证实际权重与期望权重是否一致
    """
    verified = []
    mismatches = []
    
    for log in logs:
        expected_weight = calculate_expected_weight(
            log['queue_low'], 
            log['ecn_low'], 
            log['ecn_high']
        )
        
        log['expected_weight'] = expected_weight
        log['match'] = (log['actual_weight'] == expected_weight)
        
        verified.append(log)
        
        if not log['match']:
            mismatches.append(log)
    
    return verified, mismatches


def generate_report(verified, mismatches, output_file):
    """
    生成验证报告 CSV
    """
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # 写入表头
        writer.writerow([
            'time_us', 'flow_name', 'path_id', 'ecn_tag',
            'queue_low', 'ecn_low', 'ecn_high',
            'actual_weight', 'expected_weight', 'match'
        ])
        
        # 写入所有记录
        for log in verified:
            writer.writerow([
                f"{log['time']:.3f}",
                log['flow_name'],
                log['path_id'],
                log['ecn_tag'],
                log['queue_low'],
                log['ecn_low'],
                log['ecn_high'],
                log['actual_weight'],
                log['expected_weight'],
                'YES' if log['match'] else 'NO'
            ])
    
    print(f"Verification report saved to: {output_file}")


def print_summary(verified, mismatches):
    """
    打印验证汇总信息
    """
    total = len(verified)
    match_count = total - len(mismatches)
    
    print(f"\n{'='*60}")
    print("ECN Weight Calculation Verification Summary")
    print(f"{'='*60}")
    print(f"Total processEv events: {total}")
    print(f"Correct calculations:   {match_count} ({100*match_count/total:.1f}%)")
    print(f"Mismatches:             {len(mismatches)} ({100*len(mismatches)/total:.1f}%)")
    
    if mismatches:
        print(f"\n{'='*60}")
        print("Mismatched Records:")
        print(f"{'='*60}")
        for log in mismatches[:10]:  # 只显示前10个
            print(f"  Time: {log['time']:.3f}us, Flow: {log['flow_name']}, Path: {log['path_id']}")
            print(f"    queue_low={log['queue_low']}, ecn_low={log['ecn_low']}, ecn_high={log['ecn_high']}")
            print(f"    Actual: {log['actual_weight']}, Expected: {log['expected_weight']}")
            print()
    
    # 权重分布统计
    print(f"\n{'='*60}")
    print("Weight Distribution:")
    print(f"{'='*60}")
    weight_dist = {}
    for log in verified:
        w = log['actual_weight']
        weight_dist[w] = weight_dist.get(w, 0) + 1
    
    for w in sorted(weight_dist.keys()):
        count = weight_dist[w]
        print(f"  Weight {w}: {count} times ({100*count/total:.1f}%)")
    
    # 队列大小范围统计
    print(f"\n{'='*60}")
    print("Queue Size Statistics:")
    print(f"{'='*60}")
    queue_lows = [log['queue_low'] for log in verified]
    print(f"  Min queue_low:  {min(queue_lows)} bytes")
    print(f"  Max queue_low:  {max(queue_lows)} bytes")
    print(f"  Avg queue_low:  {sum(queue_lows)/len(queue_lows):.0f} bytes")
    
    # ECN 阈值
    if verified:
        print(f"\n  ECN Low Threshold:  {verified[0]['ecn_low']} bytes")
        print(f"  ECN High Threshold: {verified[0]['ecn_high']} bytes")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 verify_ecn_weight.py <result.txt> [output.csv]")
        print("\nExample:")
        print("  python3 verify_ecn_weight.py result.txt ecn_weight_verification.csv")
        sys.exit(1)
    
    result_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'ecn_weight_verification.csv'
    
    # 解析日志
    print(f"Parsing {result_file}...")
    logs = parse_processEv_logs(result_file)
    
    if not logs:
        print("No Hashx processEvECN logs found in result file!")
        sys.exit(1)
    
    print(f"Found {len(logs)} processEv events")
    
    # 验证权重计算
    verified, mismatches = verify_weights(logs)
    
    # 生成报告
    generate_report(verified, mismatches, output_file)
    
    # 打印汇总
    print_summary(verified, mismatches)


if __name__ == '__main__':
    main()