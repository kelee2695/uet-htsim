#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析 cwnd_events.txt，将三个流的窗口操作分成三个表
"""

import re
import sys
import os
from collections import defaultdict

def parse_cwnd_events(filename):
    """解析窗口事件文件"""
    
    # 存储每个流的事件
    flow_events = defaultdict(list)
    
    # 正则表达式匹配事件行
    # 格式: [NSCC] t=0.000000 flow=1000000001 INIT 207500->240426
    pattern = r'\[(\w+)\]\s+t=([\d.]+)\s+flow=(\d+)\s+(\w+)\s+(\d+)->(\d+)'
    
    with open(filename, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            match = re.match(pattern, line)
            if match:
                algo, time, flow_id, op_type, cwnd_before, cwnd_after = match.groups()
                flow_id = int(flow_id)
                
                event = {
                    'time': float(time),
                    'algo': algo,
                    'op_type': op_type,
                    'cwnd_before': int(cwnd_before),
                    'cwnd_after': int(cwnd_after),
                    'change': int(cwnd_after) - int(cwnd_before)
                }
                flow_events[flow_id].append(event)
    
    return flow_events

def write_flow_csv(flow_id, events, flow_name, output_dir):
    """将单个流的窗口操作表写入 CSV 文件"""
    
    # 操作类型到中文的映射
    op_type_names = {
        'INIT': '初始化',
        'BOUNDS_MAX': '上限约束',
        'BOUNDS_MIN': '下限约束',
        'FULFILL_INC': '累积增加',
        'NACK_DEC': 'NACK减少',
        'FAST_INC': '快速增加',
        'ETA_INC': '保底增加',
        'MULTI_DEC': '乘性减少',
        'QUICK_ADAPT': '快速适应'
    }
    
    # CSV 文件路径
    csv_filename = os.path.join(output_dir, f"{flow_name}_cwnd_events.csv")
    
    with open(csv_filename, 'w', encoding='utf-8') as csv_file:
        # 写入 CSV 表头
        csv_file.write("序号,时间(us),操作类型,操作中文,窗口前,窗口后,变化量\n")
        
        # 写入数据行
        for i, event in enumerate(events, 1):
            op_name = op_type_names.get(event['op_type'], event['op_type'])
            csv_file.write(f"{i},{event['time']:.3f},{event['op_type']},{op_name},"
                          f"{event['cwnd_before']},{event['cwnd_after']},{event['change']}\n")
    
    print(f"  {flow_name}: {len(events)} 个事件 -> {csv_filename}")
    return csv_filename

def main():
    if len(sys.argv) < 2:
        filename = "/home/lrh/uet-htsim/test_hw/8tor_4agg_1core_16/result_test/nscc/cwnd_events.txt"
    else:
        filename = sys.argv[1]
    
    # 生成输出文件名
    base_name = os.path.splitext(filename)[0]
    output_filename = f"{base_name}_parsed.txt"
    
    print(f"解析文件: {filename}")
    print(f"输出文件: {output_filename}")
    
    # 解析事件
    flow_events = parse_cwnd_events(filename)
    
    # 流ID到名称的映射（根据connection matrix）
    flow_names = {
        1000000001: "Uec_0_2",
        1000000003: "Uec_1_10", 
        1000000005: "Uec_9_10"
    }
    
    # 创建输出目录
    output_dir = os.path.dirname(filename)
    
    print(f"生成 CSV 文件:")
    csv_files = []
    
    # 按流ID排序，为每个流生成一个 CSV 文件
    for flow_id in sorted(flow_events.keys()):
        events = flow_events[flow_id]
        flow_name = flow_names.get(flow_id, f"Unknown_{flow_id}")
        csv_file = write_flow_csv(flow_id, events, flow_name, output_dir)
        csv_files.append(csv_file)
    
    # 生成汇总统计 CSV
    summary_filename = os.path.join(output_dir, "cwnd_events_summary.csv")
    with open(summary_filename, 'w', encoding='utf-8') as summary_file:
        summary_file.write("流名称,Flow ID,事件总数\n")
        total_events = 0
        for flow_id in sorted(flow_events.keys()):
            flow_name = flow_names.get(flow_id, f"Unknown_{flow_id}")
            event_count = len(flow_events[flow_id])
            total_events += event_count
            summary_file.write(f"{flow_name},{flow_id},{event_count}\n")
        summary_file.write(f"总计,ALL,{total_events}\n")
    
    print(f"\n汇总统计: {summary_filename}")
    print(f"解析完成，共生成 {len(csv_files) + 1} 个 CSV 文件")

if __name__ == "__main__":
    main()