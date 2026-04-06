#!/usr/bin/env python3

import os
import re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import argparse
from pathlib import Path

def parse_roce_result(result_file):
    """解析ROCE仿真结果文件"""
    data = {
        'experiment_name': '',
        'connections': 0,
        'fcts': [],
        'flow_sizes': {},
        'flow_names': []
    }
    
    with open(result_file, 'r') as f:
        for line in f:
            # 提取连接数
            if 'Connections:' in line:
                match = re.search(r'Connections:\s*(\d+)', line)
                if match:
                    data['connections'] = int(match.group(1))
            
            # 提取流完成信息: Flow Roce_X_Y finished at FCT total bytes SIZE
            if 'finished at' in line and 'total bytes' in line:
                match = re.search(r'Flow\s+(\S+)\s+\d+\s+finished at\s+([\d.]+)\s+total bytes\s+(\d+)', line)
                if match:
                    flow_name = match.group(1)
                    fct = float(match.group(2))
                    total_bytes = int(match.group(3))
                    
                    data['fcts'].append(fct)
                    data['flow_names'].append(flow_name)
                    data['flow_sizes'][flow_name] = total_bytes
    
    return data

def analyze_single_experiment(result_file, output_dir):
    """分析单个实验"""
    data = parse_roce_result(result_file)
    
    if not data['fcts']:
        print(f"警告: {result_file} 没有找到流完成数据")
        return None
    
    # 保存FCT数据
    fct_file = os.path.join(output_dir, 'fct_data.csv')
    with open(fct_file, 'w') as f:
        f.write("flow_name,fct_us,flow_size_bytes\n")
        for flow_name, fct in zip(data['flow_names'], data['fcts']):
            flow_size = data['flow_sizes'].get(flow_name, 0)
            f.write(f"{flow_name},{fct},{flow_size}\n")
    
    # 计算统计信息
    stats = {
        'total_connections': data['connections'],
        'completed_flows': len(data['fcts']),
        'mean_fct': np.mean(data['fcts']),
        'median_fct': np.median(data['fcts']),
        'min_fct': np.min(data['fcts']),
        'max_fct': np.max(data['fcts']),
        'p95_fct': np.percentile(data['fcts'], 95),
        'p99_fct': np.percentile(data['fcts'], 99),
        'std_fct': np.std(data['fcts'])
    }
    
    # 保存统计信息
    stats_file = os.path.join(output_dir, 'fct_stats.txt')
    with open(stats_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("ROCE FCT 统计信息\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"实验: {os.path.basename(output_dir)}\n")
        f.write("-" * 80 + "\n")
        f.write(f"连接数: {stats['total_connections']}\n")
        f.write(f"实际完成连接数: {stats['completed_flows']}\n")
        
        if stats['total_connections'] != stats['completed_flows']:
            f.write(f"[FAIL] 连接数不匹配!\n")
        else:
            f.write(f"[PASS] 连接数匹配\n")
        
        f.write(f"\nFCT统计:\n")
        f.write(f"  平均FCT: {stats['mean_fct']:.2f} us\n")
        f.write(f"  最小FCT: {stats['min_fct']:.2f} us\n")
        f.write(f"  最大FCT (Tail): {stats['max_fct']:.2f} us\n")
        f.write(f"  中位数FCT: {stats['median_fct']:.2f} us\n")
        f.write(f"  P95: {stats['p95_fct']:.2f} us\n")
        f.write(f"  P99: {stats['p99_fct']:.2f} us\n")
        f.write(f"  标准差: {stats['std_fct']:.2f} us\n")
    
    print(f"  完成: {stats['completed_flows']}/{stats['total_connections']} 流")
    print(f"  FCT: {stats['mean_fct']:.2f} us (平均), {stats['max_fct']:.2f} us (最大)")
    
    return data, stats

def plot_fct_cdf(experiments_data, output_dir):
    """绘制FCT的CDF图 - 标注tail FCT (最大FCT)"""
    plt.figure(figsize=(12, 8))
    
    for exp_name, (data, stats) in experiments_data.items():
        if data['fcts']:
            fcts_sorted = sorted(data['fcts'])
            cdf = np.arange(1, len(fcts_sorted) + 1) / len(fcts_sorted)
            max_fct = max(data['fcts'])
            plt.plot(fcts_sorted, cdf, marker='.', markersize=2, linestyle='-', linewidth=1.0,
                    label=f'{exp_name}, tail FCT ({max_fct:.2f} us)')
    
    plt.title('ECDF for FCTs')
    plt.xlabel('FCT (us)')
    plt.ylabel('CDF')
    plt.legend(loc='best', bbox_to_anchor=(1.02, 1), borderaxespad=0.1, fontsize=8)
    plt.grid(True)
    plt.tight_layout()
    
    output_file = os.path.join(output_dir, 'fcts_cdf.png')
    plt.savefig(output_file, format='png', dpi=300)
    plt.close()
    print(f"\n生成图表: {output_file}")

def plot_fct_comparison(experiments_data, output_dir):
    """绘制FCT对比柱状图"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    exp_names = list(experiments_data.keys())
    mean_fcts = [experiments_data[e][1]['mean_fct'] for e in exp_names]
    max_fcts = [experiments_data[e][1]['max_fct'] for e in exp_names]
    
    # 平均FCT
    axes[0].bar(exp_names, mean_fcts, color='steelblue')
    axes[0].set_title('平均 FCT', fontsize=12)
    axes[0].set_ylabel('FCT (us)')
    axes[0].tick_params(axis='x', rotation=45)
    for i, v in enumerate(mean_fcts):
        axes[0].text(i, v, f'{v:.1f}', ha='center', va='bottom', fontsize=9)
    
    # 最大FCT (Tail)
    axes[1].bar(exp_names, max_fcts, color='indianred')
    axes[1].set_title('最大 FCT (Tail)', fontsize=12)
    axes[1].set_ylabel('FCT (us)')
    axes[1].tick_params(axis='x', rotation=45)
    for i, v in enumerate(max_fcts):
        axes[1].text(i, v, f'{v:.1f}', ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    
    output_file = os.path.join(output_dir, 'fct_comparison.png')
    plt.savefig(output_file, dpi=150)
    plt.close()
    print(f"生成图表: {output_file}")

def generate_summary(experiments_data, output_dir):
    """生成统计摘要文件 - 模仿UEC脚本格式"""
    summary_file = os.path.join(output_dir, 'experiment_summary.txt')
    with open(summary_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("实验统计摘要\n")
        f.write("=" * 80 + "\n\n")
        
        for exp_name, (data, stats) in experiments_data.items():
            f.write(f"实验: {exp_name}\n")
            f.write("-" * 80 + "\n")
            f.write(f"连接数: {stats['total_connections']}\n")
            f.write(f"实际完成连接数: {stats['completed_flows']}\n")
            
            if stats['total_connections'] != stats['completed_flows']:
                f.write(f"[FAIL] 连接数不匹配!\n")
            else:
                f.write(f"[PASS] 连接数匹配\n")
            
            f.write(f"FCT统计:\n")
            f.write(f"  平均FCT: {stats['mean_fct']:.2f} us\n")
            f.write(f"  最小FCT: {stats['min_fct']:.2f} us\n")
            f.write(f"  最大FCT (Tail): {stats['max_fct']:.2f} us\n")
            f.write(f"  中位数FCT: {stats['median_fct']:.2f} us\n")
            f.write(f"  P95: {stats['p95_fct']:.2f} us\n")
            f.write(f"  P99: {stats['p99_fct']:.2f} us\n")
            f.write(f"  标准差: {stats['std_fct']:.2f} us\n")
            f.write("\n")
    
    print(f"生成统计摘要: {summary_file}")

def main():
    parser = argparse.ArgumentParser(description='分析ROCE仿真结果的FCT')
    parser.add_argument('-i', '--input', help='单个结果文件路径')
    parser.add_argument('-o', '--output', help='输出目录')
    parser.add_argument('-d', '--dir', help='批量分析目录')
    args = parser.parse_args()
    
    if args.dir:
        # 批量分析
        result_dir = args.dir
        output_dir = args.output if args.output else os.path.join(result_dir, 'figures')
        os.makedirs(output_dir, exist_ok=True)
        
        experiments_data = {}
        
        print("=" * 80)
        print("实验结果分析工具")
        print("=" * 80)
        print(f"结果目录: {result_dir}")
        print(f"输出目录: {output_dir}")
        print("=" * 80)
        print()
        
        for item in sorted(os.listdir(result_dir)):
            item_path = os.path.join(result_dir, item)
            if not os.path.isdir(item_path):
                continue
            
            result_file = os.path.join(item_path, 'result.txt')
            if os.path.exists(result_file):
                print(f"解析实验: {item}")
                print(f"  连接数: {experiments_data.get(item, ({}, {'connections': 0}))[1].get('connections', 0)}, 实际完成: {experiments_data.get(item, ({}, {'completed_flows': 0}))[1].get('completed_flows', 0)}")
                result = analyze_single_experiment(result_file, item_path)
                if result:
                    experiments_data[item] = result
                    data, stats = result
                    print(f"  FCT范围: {min(data['fcts']):.2f} - {max(data['fcts']):.2f} us")
                    print()
        
        if experiments_data:
            plot_fct_cdf(experiments_data, output_dir)
            plot_fct_comparison(experiments_data, output_dir)
            generate_summary(experiments_data, output_dir)
            
            # 生成CSV格式的详细数据 - 模仿UEC格式
            csv_file = os.path.join(output_dir, 'experiment_details.csv')
            with open(csv_file, 'w') as f:
                f.write("Experiment,Connections,Actual_Connections,Mean_FCT_us,Min_FCT_us,Max_FCT_us,Median_FCT_us,"
                        "P95_FCT_us,P99_FCT_us,Std_FCT_us\n")
                
                for exp_name, (data, stats) in experiments_data.items():
                    f.write(f"{exp_name},{stats['total_connections']},{stats['completed_flows']},"
                            f"{stats['mean_fct']:.2f},{stats['min_fct']:.2f},{stats['max_fct']:.2f},"
                            f"{stats['median_fct']:.2f},{stats['p95_fct']:.2f},{stats['p99_fct']:.2f},"
                            f"{stats['std_fct']:.2f}\n")
            
            print(f"生成详细数据CSV: {csv_file}")
        
        print("\n" + "=" * 80)
        print("分析完成！")
        print(f"结果保存在: {output_dir}")
        print("=" * 80)
    
    elif args.input and args.output:
        # 单个文件分析
        os.makedirs(args.output, exist_ok=True)
        print(f"分析文件: {args.input}")
        analyze_single_experiment(args.input, args.output)
        print("分析完成！")
    
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
