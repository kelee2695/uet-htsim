#!/usr/bin/env python3
import os
import re
import argparse
import matplotlib.pyplot as plt
import numpy as np


def parse_log_file(filepath):
    """解析日志文件，返回每个队列每次统计的累积到达包数"""
    queue_names = {}
    queue_samples = {}

    with open(filepath, 'r') as f:
        for line in f:
            id_match = re.search(r'ID (\d+)', line)
            if not id_match:
                continue
            queue_id = int(id_match.group(1))

            name_match = re.search(r'Name (\S+)', line)
            if name_match:
                queue_names[queue_id] = name_match.group(1)

            if 'Ev CUM_TRAFFIC' in line:
                time_match = re.search(r'^(\d+\.\d+)', line)
                timestamp = float(time_match.group(1)) if time_match else 0.0
                
                match = re.search(r'CumArr (\d+)', line)
                if match:
                    cum_arr = int(match.group(1))
                    queue_samples.setdefault(queue_id, []).append((timestamp, cum_arr))

    return {'names': queue_names, 'samples': queue_samples}


def normalize_queue_name(name):
    """统一队列名称格式：US0->LS_0(0) → US0->LS0(0)"""
    return re.sub(r'LS_(\d+)', r'LS\1', name)


def parse_queue_name(name):
    """解析队列名，返回排序键 (leaf_id, type_order, target_id, queue_idx)"""
    normalized = normalize_queue_name(name)
    
    patterns = [
        (r'LS(\d+)->DST(\d+)\((\d+)\)', 0),   # LS->DST
        (r'LS(\d+)->US(\d+)\((\d+)\)', 1),    # LS->US
        (r'LS(\d+)->CS(\d+)\((\d+)\)', 2),    # LS->CS
        (r'SRC(\d+)->LS(\d+)\((\d+)\)', 3),   # SRC->LS
        (r'US(\d+)->LS(\d+)\((\d+)\)', 4),    # US->LS
    ]
    
    for pattern, type_order in patterns:
        match = re.search(pattern, normalized)
        if match:
            ids = [int(m) for m in match.groups()]
            if type_order == 3:  # SRC->LS: (leaf_id, type, src_id, qidx)
                return (ids[1], type_order, ids[0], ids[2])
            elif type_order == 4:  # US->LS: (leaf_id, type, us_id, qidx)
                return (ids[1], type_order, ids[0], ids[2])
            else:  # LS->xxx: (leaf_id, type, target_id, qidx)
                return (ids[0], type_order, ids[1], ids[2])
    
    return (9999, 99, 9999, 0)


def calculate_jain_index(values):
    """计算Jain公平指数: (sum(x_i))^2 / (n * sum(x_i^2))"""
    n = len(values)
    if n == 0 or sum(values) == 0:
        return 1.0  # 如果没有数据或全为0，视为完全公平
    
    sum_x = sum(values)
    sum_x2 = sum(x ** 2 for x in values)
    
    if sum_x2 == 0:
        return 1.0
    
    jain = (sum_x ** 2) / (n * sum_x2)
    return jain


def get_leaf_us_queues(queue_names, leaf_id):
    """获取指定叶交换机到US0和US1的队列"""
    prefix1 = f'LS{leaf_id}->US0('
    prefix2 = f'LS{leaf_id}->US1('
    return [q for q in queue_names if q.startswith(prefix1) or q.startswith(prefix2)]


def generate_csv(exp_dir, data):
    """生成CSV文件：每时间片新增包数 + 每个叶交换机的Jain指数 + 总包数"""
    names = data['names']
    samples = data['samples']
    
    # 统一队列名并去重
    queue_names = list({normalize_queue_name(names[qid]) for qid in samples if qid in names})
    queue_names.sort(key=parse_queue_name)
    
    # 为每个叶交换机获取上行队列（LS0-LS3）
    leaf_queues = {}
    for leaf_id in range(4):
        leaf_queues[leaf_id] = get_leaf_us_queues(queue_names, leaf_id)
    
    # 收集所有时间戳
    timestamps = sorted({ts for qid in samples for ts, _ in samples[qid]})
    
    # 构建数据: timestamp -> {queue_name -> cum_arr}
    data_by_time = {ts: {} for ts in timestamps}
    for qid, sample_list in samples.items():
        if qid not in names:
            continue
        qname = normalize_queue_name(names[qid])
        for ts, cum_arr in sample_list:
            data_by_time[ts][qname] = data_by_time[ts].get(qname, 0) + cum_arr
    
    # 计算区间包数和总包数
    interval_data = []
    last_vals = {}
    totals = {}
    
    for ts in timestamps:
        row = {'timestamp': ts}
        for qname in queue_names:
            cum = data_by_time[ts].get(qname, 0)
            interval = cum - last_vals.get(qname, 0)
            row[qname] = interval
            last_vals[qname] = cum
            totals[qname] = cum
        
        # 计算每个叶交换机的Jain指数
        for leaf_id in range(4):
            us_queues = leaf_queues[leaf_id]
            us_values = [row.get(q, 0) for q in us_queues]
            row[f'Jain_Index_LS{leaf_id}'] = calculate_jain_index(us_values)
        
        interval_data.append(row)
    
    # 写入CSV
    output_file = os.path.join(exp_dir, 'queue_traffic.csv')
    with open(output_file, 'w') as f:
        # 表头：所有队列名 + 每个叶交换机的Jain_Index
        jain_headers = [f'Jain_Index_LS{i}' for i in range(4)]
        f.write('Timestamp,' + ','.join(queue_names) + ',' + ','.join(jain_headers) + '\n')
        
        # 数据行
        for row in interval_data:
            line = str(row['timestamp']) + ',' + ','.join(str(row.get(q, 0)) for q in queue_names)
            for leaf_id in range(4):
                line += ',' + str(round(row[f'Jain_Index_LS{leaf_id}'], 4))
            f.write(line + '\n')
        
        # 总包数行（也计算每个叶交换机的Jain指数）
        total_line = 'Total,' + ','.join(str(totals.get(q, 0)) for q in queue_names)
        for leaf_id in range(4):
            total_values = [totals.get(q, 0) for q in leaf_queues[leaf_id]]
            total_jain = calculate_jain_index(total_values)
            total_line += ',' + str(round(total_jain, 4))
        total_line += '\n'
        f.write(total_line)
    
    print(f"Saved: {output_file}")
    return output_file


def analyze_experiment(exp_dir, exp_name):
    """分析单个实验"""
    log_file = os.path.join(exp_dir, 'result_parsed.log')
    if not os.path.exists(log_file):
        print(f"Skip {exp_name}: no result_parsed.log")
        return None

    data = parse_log_file(log_file)
    if not data:
        return None

    output_file = generate_csv(exp_dir, data)
    return {'name': exp_name, 'output_file': output_file}


def read_jain_indices(csv_file):
    """从CSV文件中读取所有时间戳的每个叶交换机的Jain指数（排除Total行）和Total行的Jain指数"""
    jain_indices_by_leaf = {i: [] for i in range(4)}  # LS0-LS3
    total_jain_by_leaf = {i: None for i in range(4)}
    
    with open(csv_file, 'r') as f:
        lines = f.readlines()
        if len(lines) < 1:
            return jain_indices_by_leaf, total_jain_by_leaf
        
        # 解析表头，找到每个Jain_Index列的位置
        header = lines[0].strip().split(',')
        jain_col_indices = {}
        for leaf_id in range(4):
            col_name = f'Jain_Index_LS{leaf_id}'
            if col_name in header:
                jain_col_indices[leaf_id] = header.index(col_name)
        
        # 跳过表头，读取数据
        for line in lines[1:]:
            parts = line.strip().split(',')
            if len(parts) > 1:
                try:
                    is_total = line.startswith('Total,')
                    for leaf_id, col_idx in jain_col_indices.items():
                        if col_idx < len(parts):
                            jain = float(parts[col_idx])
                            if is_total:
                                total_jain_by_leaf[leaf_id] = jain
                            else:
                                jain_indices_by_leaf[leaf_id].append(jain)
                except ValueError:
                    continue
    
    return jain_indices_by_leaf, total_jain_by_leaf


def generate_boxplot_for_leaf(parent_dir, results, leaf_id):
    """为指定叶交换机生成箱线图总结"""
    # 创建概要目录
    summary_dir = os.path.join(parent_dir, '概要')
    os.makedirs(summary_dir, exist_ok=True)
    
    # 收集每个实验的Jain指数数据和Total Jain指数
    exp_names = []
    jain_data = []
    total_jain_values = []
    
    for result in results:
        csv_file = result['output_file']
        if csv_file and os.path.exists(csv_file):
            jain_indices_by_leaf, total_jain_by_leaf = read_jain_indices(csv_file)
            jain_indices = jain_indices_by_leaf.get(leaf_id, [])
            total_jain = total_jain_by_leaf.get(leaf_id)
            if jain_indices:
                exp_names.append(result['name'])
                jain_data.append(jain_indices)
                total_jain_values.append(total_jain if total_jain is not None else np.nan)
    
    if not jain_data:
        print(f"No Jain index data found for LS{leaf_id}")
        return
    
    # 创建图形
    fig, ax = plt.subplots(figsize=(max(14, len(exp_names) * 1.2), 7))
    
    # 绘制箱线图
    bp = ax.boxplot(jain_data, labels=exp_names, patch_artist=True, positions=range(1, len(exp_names) + 1))
    
    # 设置箱体颜色
    colors = plt.cm.Set3(np.linspace(0, 1, len(exp_names)))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
    
    # 计算并标注均值（在箱体右侧）
    for i, (data, name) in enumerate(zip(jain_data, exp_names), 1):
        mean_val = np.mean(data)
        ax.text(i + 0.35, mean_val, f'{mean_val:.3f}', 
                ha='left', va='center', fontsize=9, color='red', fontweight='bold')
    
    # 在同一图上绘制Total Jain指数的折线图
    x_positions = range(1, len(exp_names) + 1)
    ax.plot(x_positions, total_jain_values, 'o-', color='darkblue', linewidth=2, 
            markersize=8, label='Total Jain Index', zorder=5)
    
    # 标注Total Jain指数的值
    for i, (x, y) in enumerate(zip(x_positions, total_jain_values)):
        if not np.isnan(y):
            ax.text(x, y + 0.03, f'{y:.3f}', ha='center', va='bottom', 
                   fontsize=9, color='darkblue', fontweight='bold')
    
    # 设置标题和标签
    ax.set_ylabel('Jain Fairness Index', fontsize=12)
    ax.set_xlabel('Experiment', fontsize=12)
    ax.set_title(f'LS{leaf_id} Jain Index Distribution (Boxplot) & Total Jain Index (Line)\n(Lower values indicate burstier traffic)', fontsize=14)
    
    # 设置y轴范围和x轴刻度
    ax.set_ylim(0, 1.15)
    ax.set_xticks(range(1, len(exp_names) + 1))
    ax.set_xticklabels(exp_names, rotation=45, ha='right')
    ax.axhline(y=1.0, color='r', linestyle='--', alpha=0.3)
    
    # 添加网格和图例
    ax.grid(True, alpha=0.3, axis='y')
    ax.legend(loc='lower right')
    
    plt.tight_layout()
    
    # 保存图片
    output_path = os.path.join(summary_dir, f'jain_index_boxplot_LS{leaf_id}.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Generated boxplot for LS{leaf_id}: {output_path}")


def generate_boxplot_summary(parent_dir, results):
    """生成箱线图总结，为每个叶交换机单独生成一张图"""
    for leaf_id in range(4):
        generate_boxplot_for_leaf(parent_dir, results, leaf_id)


def main():
    parser = argparse.ArgumentParser(description='Queue Traffic Analysis Tool')
    parser.add_argument('-i', '--input', required=True, help='Input experiment directory')
    parser.add_argument('-e', '--experiments', nargs='+', help='Specific experiments to analyze')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Directory not found: {args.input}")
        return

    exp_names = args.experiments or [
        d for d in os.listdir(args.input)
        if os.path.isdir(os.path.join(args.input, d))
        and not d.startswith('.')
        and os.path.exists(os.path.join(args.input, d, 'result_parsed.log'))
    ]

    print(f"Found {len(exp_names)} experiments")
    
    results = []
    for name in sorted(exp_names):
        print(f"Analyzing: {name}...")
        result = analyze_experiment(os.path.join(args.input, name), name)
        if result:
            results.append(result)

    print(f"\nGenerated {len(results)} CSV files:")
    for r in results:
        print(f"  - {r['output_file']}")
    
    # 生成箱线图总结
    if results:
        generate_boxplot_summary(args.input, results)


if __name__ == '__main__':
    main()