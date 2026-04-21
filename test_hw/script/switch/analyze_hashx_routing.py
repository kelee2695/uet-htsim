#!/usr/bin/env python3
"""
分析 HASHX 路由选路行为，统计：
1. UecMpHashx 的 pathid 选择分布
2. FatTreeSwitch 的 HASHX 选路分布（按交换机ID分组）
使用方法: python3 analyze_hashx_routing.py -i <输入文件>
"""

import argparse
import re
import os
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
from collections import defaultdict, Counter

def parse_logs(filename):
    """
    解析两种日志：
    1. UecMpHashx: "Hashx nextEntropy selected_path X weight Y next_path Z"
    2. FatTreeSwitch: "[HASHX DEBUG] TOR/SPINE switch_id=X pathid=Y available_ports=Z selected_port=W"
    """
    # 正则表达式
    uec_mp_pattern = r'Hashx nextEntropy selected_path (\d+)'
    hashx_debug_pattern = r'\[HASHX DEBUG\] (TOR|SPINE) switch_id=(\d+) pathid=\d+ available_ports=\d+ selected_port=(\d+)'
    
    # 数据结构
    uec_mp_paths = Counter()  # UecMpHashx 选中的 path
    switch_stats = defaultdict(lambda: defaultdict(Counter))  # {switch_id: {'TOR'/'SPINE': {port: count}}}
    
    line_count = 0
    uec_mp_count = 0
    hashx_count = 0
    
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line_count += 1
            
            # 匹配 UecMpHashx 日志
            uec_match = re.search(uec_mp_pattern, line)
            if uec_match:
                uec_mp_count += 1
                selected_path = int(uec_match.group(1))
                uec_mp_paths[selected_path] += 1
                continue
            
            # 匹配 HASHX DEBUG 日志
            hashx_match = re.search(hashx_debug_pattern, line)
            if hashx_match:
                hashx_count += 1
                switch_type = hashx_match.group(1)
                switch_id = int(hashx_match.group(2))
                selected_port = int(hashx_match.group(3))
                switch_stats[switch_id][switch_type][selected_port] += 1
    
    print(f"总共处理 {line_count} 行")
    print(f"匹配到 {uec_mp_count} 条 UecMpHashx 记录")
    print(f"匹配到 {hashx_count} 条 HASHX DEBUG 记录")
    
    return uec_mp_paths, switch_stats

def plot_uec_mp_paths(path_counts, output_dir):
    """
    绘制 UecMpHashx 选中的 path 分布柱状图（所有 path 放一起）
    """
    if not path_counts:
        print("没有 UecMpHashx 路径数据")
        return
    
    # 排序 path
    paths = sorted(path_counts.keys())
    counts = [path_counts[p] for p in paths]
    
    # 创建图表
    fig, ax = plt.subplots(figsize=(16, 8))
    
    bars = ax.bar(paths, counts, color='coral', edgecolor='black', alpha=0.7)
    
    # 添加数值标签
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        if height > max(counts) * 0.03:
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(count)}',
                   ha='center', va='bottom', fontsize=6, rotation=90)
    
    ax.set_xlabel('Selected Path (UecMpHashx)', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title('UecMpHashx Path Selection Distribution\n(All Paths Combined)', fontsize=14)
    ax.set_xticks(paths)
    ax.set_xticklabels([str(p) for p in paths], rotation=45, ha='right')
    
    # 添加网格线
    ax.yaxis.grid(True, linestyle='--', alpha=0.7)
    
    # 添加统计信息
    total = sum(counts)
    avg = total / len(paths) if paths else 0
    max_count = max(counts) if counts else 0
    min_count = min(counts) if counts else 0
    std = (sum((c - avg)**2 for c in counts) / len(counts))**0.5 if counts else 0
    
    stats_text = f'Total: {total}\nPaths: {len(paths)}\nAvg: {avg:.1f}\nMax: {max_count}\nMin: {min_count}\nStd: {std:.1f}'
    ax.text(0.98, 0.98, stats_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    
    # 保存图片
    output_file = os.path.join(output_dir, 'uec_mp_path_distribution.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Saved: {output_file}")

def plot_all_switches_grid(switch_stats, output_dir):
    """
    为每个交换机单独绘制一张图，所有图拼成一张大图（2x2布局）
    """
    if not switch_stats:
        print("没有交换机路由数据")
        return
    
    # 收集所有交换机和类型的数据
    all_plots = []
    for switch_id in sorted(switch_stats.keys()):
        for switch_type in ['TOR', 'SPINE']:
            port_counts = switch_stats[switch_id].get(switch_type, {})
            if port_counts:
                all_plots.append((switch_id, switch_type, port_counts))
    
    if not all_plots:
        return
    
    # 计算需要的子图数量
    n_plots = len(all_plots)
    n_cols = 2
    n_rows = (n_plots + n_cols - 1) // n_cols
    
    # 创建大图
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 6 * n_rows))
    if n_plots == 1:
        axes = [axes]
    else:
        axes = axes.flatten() if n_rows > 1 else axes.flatten()
    
    for idx, (switch_id, switch_type, port_counts) in enumerate(all_plots):
        ax = axes[idx] if n_plots > 1 else axes[0]
        
        ports = sorted(port_counts.keys())
        counts = [port_counts[p] for p in ports]
        
        bars = ax.bar(ports, counts, color='steelblue', edgecolor='black', alpha=0.7)
        
        # 添加数值标签
        for bar, count in zip(bars, counts):
            height = bar.get_height()
            if height > max(counts) * 0.05:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(count)}',
                       ha='center', va='bottom', fontsize=6, rotation=90)
        
        ax.set_xlabel('Selected Port', fontsize=10)
        ax.set_ylabel('Count', fontsize=10)
        ax.set_title(f'Switch {switch_id} ({switch_type})', fontsize=12)
        ax.set_xticks(ports)
        ax.set_xticklabels([str(p) for p in ports], rotation=45, ha='right', fontsize=8)
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        
        # 添加统计信息
        total = sum(counts)
        avg = total / len(ports) if ports else 0
        max_count = max(counts) if counts else 0
        min_count = min(counts) if counts else 0
        
        stats_text = f'Total: {total}\nAvg: {avg:.1f}\nMax: {max_count}\nMin: {min_count}'
        ax.text(0.97, 0.97, stats_text, transform=ax.transAxes,
                fontsize=8, verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 隐藏多余的子图
    for idx in range(n_plots, len(axes) if isinstance(axes, list) else 1):
        if n_plots > 1:
            axes[idx].axis('off')
    
    plt.suptitle('HASHX Routing Distribution by Switch', fontsize=16, y=1.00)
    plt.tight_layout()
    
    output_file = os.path.join(output_dir, 'all_switches_routing_grid.png')
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
    uec_mp_paths, switch_stats = parse_logs(input_file)
    
    if not uec_mp_paths and not switch_stats:
        print("未找到任何日志记录，请检查文件格式")
        return
    
    print(f"\n发现 {len(switch_stats)} 个交换机")
    
    # 1. 绘制 UecMpHashx 路径分布图（所有 path 放一起）
    if uec_mp_paths:
        print(f"\nUecMpHashx 路径统计:")
        print(f"  总共 {sum(uec_mp_paths.values())} 次路径选择")
        print(f"  使用了 {len(uec_mp_paths)} 个不同路径")
        plot_uec_mp_paths(uec_mp_paths, output_dir)
    
    # 2. 绘制交换机 HASHX 选路分布图（每个交换机单独一张图，拼成一张大图）
    if switch_stats:
        print(f"\n绘制交换机路由分布图...")
        plot_all_switches_grid(switch_stats, output_dir)
    
    # 生成汇总统计
    summary_file = os.path.join(output_dir, 'routing_summary.txt')
    with open(summary_file, 'w') as f:
        f.write("HASHX Routing Analysis Summary\n")
        f.write("=" * 60 + "\n\n")
        
        # UecMpHashx 统计
        if uec_mp_paths:
            f.write("UecMpHashx Path Selection:\n")
            f.write("-" * 40 + "\n")
            total = sum(uec_mp_paths.values())
            paths = len(uec_mp_paths)
            avg = total / paths if paths else 0
            max_p = max(uec_mp_paths.values()) if uec_mp_paths else 0
            min_p = min(uec_mp_paths.values()) if uec_mp_paths else 0
            f.write(f"  Total selections: {total}\n")
            f.write(f"  Unique paths: {paths}\n")
            f.write(f"  Average per path: {avg:.2f}\n")
            f.write(f"  Max: {max_p}, Min: {min_p}\n")
            f.write(f"  Path distribution: {dict(sorted(uec_mp_paths.items()))}\n\n")
        
        # 交换机统计
        if switch_stats:
            f.write("Switch HASHX Routing:\n")
            f.write("=" * 60 + "\n")
            
            for switch_id in sorted(switch_stats.keys()):
                f.write(f"\nSwitch ID: {switch_id}\n")
                f.write("-" * 40 + "\n")
                
                for switch_type in ['TOR', 'SPINE']:
                    port_counts = switch_stats[switch_id].get(switch_type, {})
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
    print(f"汇总统计已保存: {summary_file}")
    print("分析完成!")

if __name__ == '__main__':
    main()