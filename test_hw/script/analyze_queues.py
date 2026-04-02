#!/usr/bin/env python3
import os
import re
import argparse
from collections import defaultdict
from datetime import datetime

def classify_queue(name):
    if not name:
        return 'Unknown'
    if '->DST' in name:
        return 'ToR_Downlink'
    elif '->LS_' in name:
        return 'ToR_Downlink'
    elif '->CS' in name:
        return 'Agg_Uplink'
    elif 'SRC' in name and '->LS' in name:
        return 'Host_Uplink'
    elif '->US' in name:
        return 'ToR_Uplink'
    return 'Unknown'

def get_switch_info(name):
    if not name:
        return 'Unknown', 'Unknown'

    tor_match = re.search(r'LS(\d+)', name)
    agg_match = re.search(r'US(\d+)', name)
    core_match = re.search(r'CS(\d+)', name)
    host_match = re.search(r'DST(\d+)|SRC(\d+)', name)

    if tor_match:
        sw_type = 'ToR'
        sw_id = f"LS{tor_match.group(1)}"
    elif agg_match:
        sw_type = 'Agg'
        sw_id = f"US{agg_match.group(1)}"
    elif core_match:
        sw_type = 'Core'
        sw_id = f"CS{core_match.group(1)}"
    elif host_match:
        sw_type = 'Host'
        sw_id = 'Host'
    else:
        sw_type = 'Unknown'
        sw_id = 'Unknown'

    return sw_type, sw_id

def get_queue_index(name):
    if not name:
        return -1
    match = re.search(r'\((\d+)\)', name)
    if match:
        return int(match.group(1))
    return -1

def parse_log_file(filepath):
    queue_max = {}
    queue_min = {}
    queue_last = {}
    queue_names = {}
    queue_cumarr = {}
    queue_cumdrop = {}

    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return None

    with open(filepath, 'r') as f:
        for line in f:
            id_match = re.search(r'ID (\d+)', line)
            if not id_match:
                continue
            queue_id = int(id_match.group(1))

            name_match = re.search(r'Name (\S+)', line)
            if name_match:
                queue_names[queue_id] = name_match.group(1)

            if 'Ev RANGE' in line:
                match = re.search(r'LastQ (\d+) MinQ (\d+) MaxQ (\d+)', line)
                if match:
                    lastq = int(match.group(1))
                    minq = int(match.group(2))
                    maxq = int(match.group(3))
                    queue_last[queue_id] = lastq
                    if queue_id not in queue_max or maxq > queue_max[queue_id]:
                        queue_max[queue_id] = maxq
                    if queue_id not in queue_min or minq < queue_min[queue_id]:
                        queue_min[queue_id] = minq

            elif 'Ev CUM_TRAFFIC' in line:
                match = re.search(r'CumArr (\d+) CumIdle (\d+) CumDrop (\d+)', line)
                if match:
                    cumarr = int(match.group(1))
                    cumdrop = int(match.group(3))
                    queue_cumarr[queue_id] = cumarr
                    if queue_id not in queue_cumdrop:
                        queue_cumdrop[queue_id] = cumdrop
                    elif cumdrop > queue_cumdrop[queue_id]:
                        queue_cumdrop[queue_id] = cumdrop

    return {
        'max': queue_max,
        'min': queue_min,
        'last': queue_last,
        'names': queue_names,
        'cumarr': queue_cumarr,
        'cumdrop': queue_cumdrop
    }

def analyze_experiment(exp_dir, exp_name):
    result_log = os.path.join(exp_dir, 'result_parsed.log')
    if not os.path.exists(result_log):
        print(f"Skip {exp_name}: no result_parsed.log")
        return None

    data = parse_log_file(result_log)
    if not data:
        return None

    queues_by_switch = {}
    queues_by_type = defaultdict(list)
    queues_by_switch_type = {}

    for qid, maxq in data['max'].items():
        name = data['names'].get(qid, f"ID_{qid}")
        sw_type, sw_id = get_switch_info(name)
        direction = classify_queue(name)
        queue_idx = get_queue_index(name)

        lastq = data['last'].get(qid, 0)
        minq = data['min'].get(qid, 0)
        cumarr = data['cumarr'].get(qid, 0)
        cumdrop = data['cumdrop'].get(qid, 0)

        queue_info = {
            'id': qid,
            'name': name,
            'type': direction,
            'switch_type': sw_type,
            'switch_id': sw_id,
            'queue_idx': queue_idx,
            'maxq': maxq,
            'lastq': lastq,
            'minq': minq,
            'cumarr': cumarr,
            'cumdrop': cumdrop
        }

        if sw_id not in queues_by_switch:
            queues_by_switch[sw_id] = {}
        if direction not in queues_by_switch[sw_id]:
            queues_by_switch[sw_id][direction] = []
        queues_by_switch[sw_id][direction].append(queue_info)

        queues_by_type[direction].append(queue_info)

        if sw_type not in queues_by_switch_type:
            queues_by_switch_type[sw_type] = {}
        if direction not in queues_by_switch_type[sw_type]:
            queues_by_switch_type[sw_type][direction] = []
        queues_by_switch_type[sw_type][direction].append(queue_info)

    return {
        'name': exp_name,
        'dir': exp_dir,
        'queues_by_switch': dict(queues_by_switch),
        'queues_by_type': dict(queues_by_type),
        'queues_by_switch_type': dict(queues_by_switch_type),
        'all_queues': [{'id': qid, 'name': data['names'].get(qid, f"ID_{qid}"),
                        'maxq': data['max'].get(qid, 0), 'cumarr': data['cumarr'].get(qid, 0)}
                       for qid in data['max'].keys()]
    }

def calculate_stats(queues):
    if not queues:
        return {'count': 0, 'avg': 0, 'std': 0, 'cv': 0, 'min': 0, 'max': 0}

    import statistics
    values = [q['maxq'] for q in queues]
    avg = statistics.mean(values) if values else 0
    std = statistics.stdev(values) if len(values) > 1 else 0
    cv = (std / avg * 100) if avg > 0 else 0

    return {
        'count': len(values),
        'avg': avg,
        'std': std,
        'cv': cv,
        'min': min(values) if values else 0,
        'max': max(values) if values else 0
    }

def generate_summary_csv(experiments, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    summary_file = os.path.join(output_dir, 'queue_summary.csv')
    with open(summary_file, 'w') as f:
        f.write("Experiment,SwitchType,Direction,Count,AvgMaxQ,StdDev,CV%,MinMaxQ,MaxMaxQ\n")

        for exp in experiments:
            for sw_type, directions in exp['queues_by_switch_type'].items():
                for direction, queues in directions.items():
                    stats = calculate_stats(queues)
                    f.write(f"{exp['name']},{sw_type},{direction},{stats['count']},"
                           f"{stats['avg']:.2f},{stats['std']:.2f},{stats['cv']:.2f},"
                           f"{stats['min']},{stats['max']}\n")

            all_queues = exp['all_queues']
            stats_all = calculate_stats([{'maxq': q['maxq']} for q in all_queues])
            f.write(f"{exp['name']},ALL,ALL,{stats_all['count']},"
                   f"{stats_all['avg']:.2f},{stats_all['std']:.2f},{stats_all['cv']:.2f},"
                   f"{stats_all['min']},{stats_all['max']}\n")

    print(f"Saved: {summary_file}")
    return summary_file

def generate_detail_csv_pivot(experiments, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    all_queue_keys = []
    for exp in experiments:
        for q in exp['all_queues']:
            name = q['name']
            sw_type, sw_id = get_switch_info(name)
            direction = classify_queue(name)
            queue_idx = get_queue_index(name)
            key = (sw_type, sw_id, direction, name)
            if key not in all_queue_keys:
                all_queue_keys.append(key)

    all_queue_keys.sort(key=lambda x: (x[0], x[1], x[2], get_queue_index(x[3])))

    PKT_SIZE = 4150

    detail_file = os.path.join(output_dir, 'queue_detail_pivot.csv')
    with open(detail_file, 'w') as f:
        header = ["SwitchType", "SwitchID", "QueueName", "Direction"]
        for exp in experiments:
            header.append(f"{exp['name']}_MaxQ_Pkt")
            header.append(f"{exp['name']}_CumPkt")
        f.write(",".join(header) + "\n")

        exp_data = {}
        for exp in experiments:
            exp_data[exp['name']] = {q['name']: q for q in exp['all_queues']}

        for sw_type, sw_id, direction, name in all_queue_keys:
            row = [sw_type, sw_id, name, direction]
            for exp in experiments:
                q_data = exp_data.get(exp['name'], {}).get(name, {})
                maxq = q_data.get('maxq', 0)
                maxq_pkt = int(maxq / PKT_SIZE) if maxq > 0 else 0
                row.append(str(maxq_pkt))
                row.append(str(q_data.get('cumarr', '')))
            f.write(",".join(row) + "\n")

    print(f"Saved: {detail_file}")
    return detail_file

def generate_detail_csv(experiments, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    all_queue_keys = []
    for exp in experiments:
        for q in exp['all_queues']:
            name = q['name']
            sw_type, sw_id = get_switch_info(name)
            direction = classify_queue(name)
            queue_idx = get_queue_index(name)
            key = (sw_type, sw_id, direction, name)
            if key not in all_queue_keys:
                all_queue_keys.append(key)

    all_queue_keys.sort(key=lambda x: (x[0], x[1], x[2], get_queue_index(x[3])))

    PKT_SIZE = 4096

    detail_file = os.path.join(output_dir, 'queue_detail.csv')
    with open(detail_file, 'w') as f:
        f.write("SwitchType,SwitchID,QueueName,Direction,QueueIdx,")
        for i, exp in enumerate(experiments):
            if i > 0:
                f.write(",")
            f.write(f"{exp['name']}_MaxQ_Pkt,{exp['name']}_CumPkt,{exp['name']}_Diff%")
        f.write("\n")

        exp_data = {}
        exp_sw_avg = {}
        for exp in experiments:
            exp_data[exp['name']] = {q['name']: q for q in exp['all_queues']}
            exp_sw_avg[exp['name']] = {}
            for sw_id, directions in exp['queues_by_switch'].items():
                all_values = []
                for direction_queues in directions.values():
                    all_values.extend([q['cumarr'] for q in direction_queues if isinstance(q, dict) and q.get('cumarr', 0) > 0])
                avg = sum(all_values) / len(all_values) if all_values else 0
                exp_sw_avg[exp['name']][sw_id] = avg

        for sw_type, sw_id, direction, name in all_queue_keys:
            queue_idx = get_queue_index(name)
            row = [sw_type, sw_id, name, direction, str(queue_idx)]
            
            for exp in experiments:
                q_data = exp_data.get(exp['name'], {}).get(name, {})
                maxq = q_data.get('maxq', 0)
                cumarr = q_data.get('cumarr', '')
                sw_avg = exp_sw_avg.get(exp['name'], {}).get(sw_id, 0)
                
                maxq_pkt = int(maxq / PKT_SIZE) if maxq > 0 else 0
                
                if cumarr != '' and sw_avg > 0:
                    diff_pct = ((cumarr - sw_avg) / sw_avg) * 100
                    row.append(str(maxq_pkt))
                    row.append(str(cumarr))
                    row.append(f"{diff_pct:+.2f}")
                else:
                    row.append(str(maxq_pkt) if maxq > 0 else '')
                    row.append(str(cumarr) if cumarr != '' else '')
                    row.append('')
            
            f.write(",".join(row) + "\n")

    print(f"Saved: {detail_file}")
    return detail_file

def generate_switch_comparison_csv(experiments, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    all_switches = []
    for exp in experiments:
        for sw_id in exp['queues_by_switch'].keys():
            if sw_id not in all_switches:
                all_switches.append(sw_id)
    all_switches.sort(key=lambda x: (x[0], int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0))

    comp_file = os.path.join(output_dir, 'switch_comparison.csv')
    with open(comp_file, 'w') as f:
        header = ["SwitchType", "SwitchID"]
        for exp in experiments:
            for direction in ['ToR_Downlink', 'Host_Uplink', 'ToR_Uplink', 'Agg_Downlink', 'Agg_Uplink']:
                header.append(f"{exp['name']}_{direction}_Avg")
                header.append(f"{exp['name']}_{direction}_CV")
        f.write(",".join(header) + "\n")

        exp_switch_data = {}
        for exp in experiments:
            exp_switch_data[exp['name']] = {}
            for sw_id, directions in exp['queues_by_switch'].items():
                exp_switch_data[exp['name']][sw_id] = {}
                for direction, queues in directions.items():
                    stats = calculate_stats(queues)
                    exp_switch_data[exp['name']][sw_id][direction] = stats

        for sw_id in all_switches:
            sw_type, _ = get_switch_info(sw_id + "_test")
            row = [sw_type, sw_id]
            for exp in experiments:
                for direction in ['ToR_Downlink', 'Host_Uplink', 'ToR_Uplink', 'Agg_Downlink', 'Agg_Uplink']:
                    stats = exp_switch_data.get(exp['name'], {}).get(sw_id, {}).get(direction, {})
                    row.append(f"{stats.get('avg', 0):.2f}" if stats else "")
                    row.append(f"{stats.get('cv', 0):.2f}" if stats else "")
            f.write(",".join(row) + "\n")

    print(f"Saved: {comp_file}")
    return comp_file

def generate_report(experiments, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    report_file = os.path.join(output_dir, 'analysis_report.txt')
    with open(report_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("Queue Distribution Analysis Report\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        f.write("## Experiments Analyzed\n")
        for exp in experiments:
            f.write(f"  - {exp['name']}\n")
        f.write("\n")

        f.write("## Overall Summary\n")
        f.write("-" * 80 + "\n")
        for exp in experiments:
            all_queues = exp['all_queues']
            stats = calculate_stats([{'maxq': q['maxq']} for q in all_queues])
            f.write(f"\n### {exp['name']}\n")
            f.write(f"  Total Queues: {stats['count']}\n")
            f.write(f"  Average MaxQ: {stats['avg']:.2f} bytes\n")
            f.write(f"  Std Dev: {stats['std']:.2f}\n")
            f.write(f"  CV: {stats['cv']:.2f}%\n")
            f.write(f"  Min MaxQ: {stats['min']}\n")
            f.write(f"  Max MaxQ: {stats['max']}\n")

            quality = "EXCELLENT" if stats['cv'] < 10 else "GOOD" if stats['cv'] < 20 else "FAIR" if stats['cv'] < 30 else "POOR"
            f.write(f"  Load Balancing Quality: {quality}\n")

        f.write("\n\n## Summary by Queue Type\n")
        f.write("-" * 80 + "\n")
        for exp in experiments:
            f.write(f"\n### {exp['name']}\n")
            for direction, queues in exp['queues_by_type'].items():
                stats = calculate_stats(queues)
                f.write(f"  {direction}: {stats['count']} queues, Avg={stats['avg']:.2f}, CV={stats['cv']:.2f}%\n")

        f.write("\n\n## Summary by Switch Type and Direction\n")
        f.write("-" * 80 + "\n")
        for exp in experiments:
            f.write(f"\n### {exp['name']}\n")
            for sw_type, directions in exp['queues_by_switch_type'].items():
                f.write(f"  {sw_type}:\n")
                for direction, queues in directions.items():
                    stats = calculate_stats(queues)
                    f.write(f"    {direction}: {stats['count']} queues, Avg={stats['avg']:.2f}, CV={stats['cv']:.2f}%\n")

        f.write("\n\n## Per-Switch Comparison\n")
        f.write("-" * 80 + "\n")

        switch_types = set()
        for exp in experiments:
            for sw_type in exp['queues_by_switch_type'].keys():
                switch_types.add(sw_type)

        for sw_type in sorted(switch_types):
            f.write(f"\n### {sw_type} Switches\n")
            f.write("| Experiment | Switch | Direction | Count | Avg MaxQ | CV% |\n")
            f.write("|------------|--------|-----------|-------|----------|-----|\n")

            for exp in experiments:
                if sw_type not in exp['queues_by_switch_type']:
                    continue
                directions = exp['queues_by_switch_type'][sw_type]

                switch_ids = set()
                for direction, queues in directions.items():
                    for q in queues:
                        switch_ids.add(q['switch_id'])

                for direction in sorted(directions.keys()):
                    queues = directions[direction]
                    switch_ids_dir = set(q['switch_id'] for q in queues)

                    for sw_id in sorted(switch_ids_dir, key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0):
                        sw_queues = [q for q in queues if q['switch_id'] == sw_id]
                        stats = calculate_stats(sw_queues)
                        f.write(f"| {exp['name']} | {sw_id} | {direction} | {stats['count']} | {stats['avg']:.0f} | {stats['cv']:.1f} |\n")

        f.write("\n")
        f.write("=" * 80 + "\n")
        f.write("End of Report\n")
        f.write("=" * 80 + "\n")

    print(f"Saved: {report_file}")
    return report_file

def main():
    parser = argparse.ArgumentParser(description='Unified Queue Analysis Tool')
    parser.add_argument('-i', '--input', required=True, help='Input experiment directory (parent of experiment folders)')
    parser.add_argument('-o', '--output', required=True, help='Output directory for results')
    parser.add_argument('-e', '--experiments', nargs='+', help='Specific experiments to analyze (default: all)')

    args = parser.parse_args()

    exp_dir = args.input
    output_dir = args.output

    if not os.path.exists(exp_dir):
        print(f"Error: Directory not found: {exp_dir}")
        return

    if args.experiments:
        exp_names = args.experiments
    else:
        exp_names = [d for d in os.listdir(exp_dir)
                    if os.path.isdir(os.path.join(exp_dir, d))
                    and not d.startswith('.')
                    and os.path.exists(os.path.join(exp_dir, d, 'result_parsed.log'))]

    print(f"Found {len(exp_names)} experiments: {exp_names}")

    experiments = []
    for exp_name in sorted(exp_names):
        exp_path = os.path.join(exp_dir, exp_name)
        print(f"Analyzing: {exp_name}...")
        result = analyze_experiment(exp_path, exp_name)
        if result:
            experiments.append(result)

    if not experiments:
        print("No valid experiments found!")
        return

    print(f"\nGenerating output files in: {output_dir}")

    generate_summary_csv(experiments, output_dir)
    generate_detail_csv(experiments, output_dir)
    generate_detail_csv_pivot(experiments, output_dir)
    generate_switch_comparison_csv(experiments, output_dir)
    generate_report(experiments, output_dir)

    print(f"\nAnalysis complete!")
    print(f"Output directory: {output_dir}")
    print(f"Files generated:")
    print(f"  - queue_summary.csv (Summary by queue type)")
    print(f"  - queue_detail.csv (Detailed data for each queue, pivot format)")
    print(f"  - queue_detail_pivot.csv (Alternative pivot format)")
    print(f"  - switch_comparison.csv (Per-switch comparison)")
    print(f"  - analysis_report.txt (Human-readable report)")

if __name__ == '__main__':
    main()
