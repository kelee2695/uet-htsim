import re
import argparse

def parse_result_file(file_path):
    """
    解析结果文件，提取每个flow的开始时间、完成时间和字节数
    """
    flow_info = []
    
    start_pattern = re.compile(r'Flow Uec_(\d+)_(\d+) flowId \d+ uecSrc \d+ starting at ([\d.]+)')
    finish_pattern = re.compile(r'Flow Uec_(\d+)_(\d+) flowId \d+ uecSrc \d+ finished at ([\d.]+) total messages \d+ total packets \d+ RTS \d+ total bytes (\d+)')
    
    flows_by_pair = {}
    
    with open(file_path, 'r') as f:
        for line in f:
            start_match = start_pattern.match(line)
            if start_match:
                sender = int(start_match.group(1))
                receiver = int(start_match.group(2))
                start_time = float(start_match.group(3))
                
                key = (sender, receiver)
                flows_by_pair[key] = {
                    'sender': sender,
                    'receiver': receiver,
                    'start_time': start_time,
                    'finish_time': None,
                    'total_bytes': None
                }
                continue
            
            finish_match = finish_pattern.match(line)
            if finish_match:
                sender = int(finish_match.group(1))
                receiver = int(finish_match.group(2))
                finish_time = float(finish_match.group(3))
                total_bytes = int(finish_match.group(4))
                
                key = (sender, receiver)
                if key in flows_by_pair:
                    flows_by_pair[key]['finish_time'] = finish_time
                    flows_by_pair[key]['total_bytes'] = total_bytes
    
    return list(flows_by_pair.values())

def calculate_node_bandwidth_weighted(flow_info):
    """
    加权计算每个节点的平均发送和接收带宽
    方法：对每个流计算瞬时带宽，然后按流的持续时间进行加权平均
    """
    send_data = {}
    recv_data = {}
    
    for flow in flow_info:
        if flow['finish_time'] is None or flow['total_bytes'] is None:
            continue
        
        sender = flow['sender']
        receiver = flow['receiver']
        start_time_us = flow['start_time']
        finish_time_us = flow['finish_time']
        total_bytes = flow['total_bytes']
        
        duration_us = finish_time_us - start_time_us
        if duration_us <= 0:
            continue
        
        instantaneous_gbps = (total_bytes * 8) / (duration_us / 1e6) / 1e9
        
        if sender not in send_data:
            send_data[sender] = {'weighted_sum': 0, 'total_weight': 0, 'total_bytes': 0, 'num_flows': 0}
        send_data[sender]['weighted_sum'] += instantaneous_gbps * duration_us
        send_data[sender]['total_weight'] += duration_us
        send_data[sender]['total_bytes'] += total_bytes
        send_data[sender]['num_flows'] += 1
        
        if receiver not in recv_data:
            recv_data[receiver] = {'weighted_sum': 0, 'total_weight': 0, 'total_bytes': 0, 'num_flows': 0}
        recv_data[receiver]['weighted_sum'] += instantaneous_gbps * duration_us
        recv_data[receiver]['total_weight'] += duration_us
        recv_data[receiver]['total_bytes'] += total_bytes
        recv_data[receiver]['num_flows'] += 1
    
    send_avg = {}
    for node_id, data in send_data.items():
        if data['total_weight'] > 0:
            weighted_avg_gbps = data['weighted_sum'] / data['total_weight']
            active_time_s = data['total_weight'] / 1e6
            send_avg[node_id] = {
                'avg_gbps': weighted_avg_gbps,
                'num_flows': data['num_flows'],
                'total_bytes': data['total_bytes'],
                'active_time': active_time_s
            }
    
    recv_avg = {}
    for node_id, data in recv_data.items():
        if data['total_weight'] > 0:
            weighted_avg_gbps = data['weighted_sum'] / data['total_weight']
            active_time_s = data['total_weight'] / 1e6
            recv_avg[node_id] = {
                'avg_gbps': weighted_avg_gbps,
                'num_flows': data['num_flows'],
                'total_bytes': data['total_bytes'],
                'active_time': active_time_s
            }
    
    return send_avg, recv_avg

def main():
    parser = argparse.ArgumentParser(description='解析网络仿真结果文件，计算每节点的发送和接收带宽（加权平均）')
    parser.add_argument('-i', '--input', required=True, help='输入结果文件路径')
    parser.add_argument('-w', '--weighted', action='store_true', help='使用加权平均计算带宽（按流持续时间加权）')
    args = parser.parse_args()
    
    flow_info = parse_result_file(args.input)
    send_bandwidth, recv_bandwidth = calculate_node_bandwidth_weighted(flow_info)
    
    completed_flows = [f for f in flow_info if f['finish_time'] is not None]
    print(f"总流数量: {len(flow_info)}")
    print(f"已完成流数量: {len(completed_flows)}")
    if completed_flows:
        max_finish_time = max(f['finish_time'] for f in completed_flows)
        min_start_time = min(f['start_time'] for f in completed_flows)
        print(f"全局时间范围: {min_start_time:.3f} - {max_finish_time:.3f} 微秒 ({(max_finish_time - min_start_time)/1e6:.3f} 秒)")
    print()
    
    print("=" * 80)
    print("每节点平均发送带宽统计（加权平均，按流持续时间加权）")
    print("=" * 80)
    print(f"{'节点ID':<10} {'流数量':<10} {'总字节数':<15} {'总活跃时间(s)':<18} {'加权平均带宽(Gbps)':<25}")
    print("-" * 80)
    
    sorted_send = sorted(send_bandwidth.items())
    total_send_gbps = 0
    for node_id, info in sorted_send:
        print(f"{node_id:<10} {info['num_flows']:<10} {info['total_bytes']:<15} {info['active_time']:<18.6f} {info['avg_gbps']:<25.6f}")
        total_send_gbps += info['avg_gbps']
    
    avg_send_gbps = total_send_gbps / len(send_bandwidth) if send_bandwidth else 0
    print("-" * 80)
    print(f"{'平均':<10} {'':<10} {'':<15} {'':<18} {avg_send_gbps:<25.6f}")
    print(f"{'总计':<10} {'':<10} {'':<15} {'':<18} {total_send_gbps:<25.6f}")
    print()
    
    print("=" * 80)
    print("每节点平均接收带宽统计（加权平均，按流持续时间加权）")
    print("=" * 80)
    print(f"{'节点ID':<10} {'流数量':<10} {'总字节数':<15} {'总活跃时间(s)':<18} {'加权平均带宽(Gbps)':<25}")
    print("-" * 80)
    
    sorted_recv = sorted(recv_bandwidth.items())
    total_recv_gbps = 0
    for node_id, info in sorted_recv:
        print(f"{node_id:<10} {info['num_flows']:<10} {info['total_bytes']:<15} {info['active_time']:<18.6f} {info['avg_gbps']:<25.6f}")
        total_recv_gbps += info['avg_gbps']
    
    avg_recv_gbps = total_recv_gbps / len(recv_bandwidth) if recv_bandwidth else 0
    print("-" * 80)
    print(f"{'平均':<10} {'':<10} {'':<15} {'':<18} {avg_recv_gbps:<25.6f}")
    print(f"{'总计':<10} {'':<10} {'':<15} {'':<18} {total_recv_gbps:<25.6f}")
    print()
    
    print("=" * 80)
    print("汇总信息")
    print("=" * 80)
    print(f"发送节点数量: {len(send_bandwidth)}")
    print(f"接收节点数量: {len(recv_bandwidth)}")
    print(f"每节点平均发送带宽: {avg_send_gbps:.6f} Gbps")
    print(f"每节点平均接收带宽: {avg_recv_gbps:.6f} Gbps")
    print(f"网络总发送带宽: {total_send_gbps:.6f} Gbps")
    print(f"网络总接收带宽: {total_recv_gbps:.6f} Gbps")
    print()
    print("说明：")
    print("- 加权平均带宽 = Σ(流带宽 × 流持续时间) / Σ(流持续时间)")
    print("- 这种方法按每个流的实际传输持续时间进行加权")
    print("- 更长时间的高带宽流对结果影响更大")

if __name__ == '__main__':
    main()