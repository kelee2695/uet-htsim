#!/usr/bin/env python3
"""
分析 HASHX 路由选路行为，统计每个交换机的端口选择分布
使用方法: python3 analyze_hashx_routing_fixed.py -i <输入文件>
"""

import argparse
import re
import os
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
from collections import defaultdict, Counter

def parse_hashx_logs(filename):
    """
    解析 HASHX DEBUG 日志
    格式: [HASHX DEBUG] TOR switch_id=0 pathid=6447 available_ports=64 selected_port=47
    """
    # 修复：使用更简单的正则表达式
    pattern = r'\[HASHX DEBUG\] (TOR|SPINE) switch_id=(\d+) pathid=\d+ available_ports=\d+ selected_port=(\d+)'
    
    # 数据结构: {switch_id: {'TOR'/'SPINE': {port: count}}}
    switch_stats = defaultdict(lambda: defaultdict(Counter))
    
    line_count = 0
    match_count = 0
    
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line_count += 1
            match = re.search(pattern, line)
            if match:
                match_count += 1
                switch_type = match.group(1)  # TOR 或 SPINE
                switch_id = int(match.group(2))
                selected_port = int(match.group(3))
                
                switch_stats[switch_id][switch_type][selected_port] += 1
    
    print(f"总共处理 {line_count} 行")
    print(f"匹配到 {match_count} 条 HASHX DEBUG 记录")
    
    return switch_stats

def plot_switch_routing(switch_id, switch_type, port_counts, output_dir):
    """
    为单个交换机绘制端口选择分布柱状图
    """
    if not port_counts:
        return
    
    # 排序端口
    ports = sorted(port_counts.keys())
    counts = [port_counts[p] for p in ports]
    
    # 创建图表
    fig, ax = plt.subplots(figsize=(14, 7))
    
    bars = ax.bar(ports, counts, color='steelblue', edgecolor='black', alpha=0.7)
    
    # 添加数值标签（只在柱子较高时显示）
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        if height > max(counts) * 0.05:  # 只显示较高的柱子
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(count)}',
                   ha='center', va='bottom', fontsize=7, rotation=90)
    
    ax.set_xlabel('Selected Port', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title(f'HASHX Routing Distribution\nSwitch {switch_id} ({switch_type})', fontsize=14)
    ax.set_xticks(ports)
    ax.set_xticklabels([str(p) for p in ports], rotation=45, ha='right')
    
    # 添加网格线
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    
    # 添加统计信息
    total = sum(counts)
    avg = total / len(ports) if ports else 0
    max_count = max(counts) if counts else 0
    min_count = min(counts) if counts else 0
    std = (sum((c - avg)**2 for c in counts) / len(counts))**0.5 if counts else 0
    
    stats_text = f'Total: {total}\nPorts: {len(ports)}\nAvg: {avg:.1f}\nMax: {max_count}\nMin: {min_count}\nStd: {std:.1f}'
    ax.text(0.98, 0.98, stats_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    
    # 保存图片
    output_file = os.path.join(output_dir, f'switch_{switch_id}_{switch_type}_routing.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Saved: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='分析 HASHX 路由选路行为')
    parser.add_argument('-i', '--input', required=True, help='输入日志文件路径')
    args = parser.parse_args()
    
    input_file = args.input
    if not os.path.exists(input_file):
        print(f"错误: 文件不存在: {input_file}")
        return
    
    # 输出目录与输入文件同目录
    output_dir = os.path.dirname(os.path.abspath(input_file))
    if not output_dir:
        output_dir = '.'
    
    print(f"解析文件: {input_file}")
    print(f"输出目录: {output_dir}")
    print()
    
    # 解析日志
    switch_stats = parse_hashx_logs(input_file)
    
    if not switch_stats:
        print("未找到 HASHX DEBUG 日志，请检查文件格式")
        return
    
    print(f"\n发现 {len(switch_stats)} 个交换机")
    
    # 为每个交换机和类型生成图表
    total_plots = 0
    for switch_id in sorted(switch_stats.keys()):
        for switch_type in ['TOR', 'SPINE']:
            port_counts = switch_stats[switch_id][switch_type]
            if port_counts:
                total = sum(port_counts.values())
                print(f"\nSwitch {switch_id} ({switch_type}): {len(port_counts)} 个端口被使用, 总选路次数: {total}")
                plot_switch_routing(switch_id, switch_type, port_counts, output_dir)
                total_plots += 1
    
    # 生成汇总统计
    summary_file = os.path.join(output_dir, 'routing_summary.txt')
    with open(summary_file, 'w') as f:
        f.write("HASHX Routing Summary\n")
        f.write("=" * 60 + "\n\n")
        
        for switch_id in sorted(switch_stats.keys()):
            f.write(f"\nSwitch ID: {switch_id}\n")
            f.write("-" * 40 + "\n")
            
            for switch_type in ['TOR', 'SPINE']:
                port_counts = switch_stats[switch_id][switch_type]
                if port_counts:
                    total = sum(port_counts.values())
                    ports = len(port_counts)
                    avg = total / ports if ports else 0
                    max_p = max(port_counts.values()) if port_counts else 0
                    min_p = min(port_counts.values()) if port_counts else 0
                    
                    f.write(f"  {switch_type}:\n")
                    f.write(f"    Total routing decisions: {total}\n")
                    f.write(f"    Ports used: {ports}\n")
                    f.write(f"    Average per port: {avg:.2f}\n")
                    f.write(f"    Max: {max_p}, Min: {min_p}\n")
                    if min_p > 0:
                        f.write(f"    Imbalance ratio (max/min): {max_p/min_p:.2f}\n")
                    f.write(f"    Port distribution: {dict(sorted(port_counts.items()))}\n")
    
    print(f"\n{'='*60}")
    print(f"生成了 {total_plots} 张图表")
    print(f"汇总统计已保存: {summary_file}")
    print("分析完成!")

if __name__ == '__main__':
    main()