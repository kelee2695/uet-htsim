import re
import argparse

def parse_result_file(file_path):
    """
    解析结果文件，提取每个flow的开始时间、完成时间和字节数
    优化：使用字典进行O(1)查找，预编译正则表达式
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

def calculate_node_bandwidth_with_concurrency(flow_info):
    """
    计算每个节点的平均发送和接收带宽
    优化：使用字典聚合数据，避免重复计算
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
        
        if sender not in send_data:
            send_data[sender] = {'flows': [], 'total_bytes': 0, 'min_start': float('inf'), 'max_finish': 0}
        send_data[sender]['flows'].append((start_time_us, finish_time_us, total_bytes))
        send_data[sender]['total_bytes'] += total_bytes
        send_data[sender]['min_start'] = min(send_data[sender]['min_start'], start_time_us)
        send_data[sender]['max_finish'] = max(send_data[sender]['max_finish'], finish_time_us)
        
        if receiver not in recv_data:
            recv_data[receiver] = {'flows': [], 'total_bytes': 0, 'min_start': float('inf'), 'max_finish': 0}
        recv_data[receiver]['flows'].append((start_time_us, finish_time_us, total_bytes))
        recv_data[receiver]['total_bytes'] += total_bytes
        recv_data[receiver]['min_start'] = min(recv_data[receiver]['min_start'], start_time_us)
        recv_data[receiver]['max_finish'] = max(recv_data[receiver]['max_finish'], finish_time_us)
    
    send_avg = {}
    for node_id, data in send_data.items():
        active_time_s = (data['max_finish'] - data['min_start']) / 1e6
        if active_time_s > 0:
            avg_gbps = (data['total_bytes'] * 8) / active_time_s / 1e9
            send_avg[node_id] = {
                'avg_gbps': avg_gbps,
                'num_flows': len(data['flows']),
                'total_bytes': data['total_bytes'],
                'active_time': active_time_s,
                'start_time': data['min_start'],
                'finish_time': data['max_finish']
            }
    
    recv_avg = {}
    for node_id, data in recv_data.items():
        active_time_s = (data['max_finish'] - data['min_start']) / 1e6
        if active_time_s > 0:
            avg_gbps = (data['total_bytes'] * 8) / active_time_s / 1e9
            recv_avg[node_id] = {
                'avg_gbps': avg_gbps,
                'num_flows': len(data['flows']),
                'total_bytes': data['total_bytes'],
                'active_time': active_time_s,
                'start_time': data['min_start'],
                'finish_time': data['max_finish']
            }
    
    return send_avg, recv_avg

def main():
    parser = argparse.ArgumentParser(description='解析网络仿真结果文件，计算每节点的发送和接收带宽')
    parser.add_argument('-i', '--input', required=True, help='输入结果文件路径')
    args = parser.parse_args()
    
    flow_info = parse_result_file(args.input)
    send_bandwidth, recv_bandwidth = calculate_node_bandwidth_with_concurrency(flow_info)
    
    completed_flows = [f for f in flow_info if f['finish_time'] is not None]
    print(f"总流数量: {len(flow_info)}")
    print(f"已完成流数量: {len(completed_flows)}")
    if completed_flows:
        max_finish_time = max(f['finish_time'] for f in completed_flows)
        print(f"最大完成时间: {max_finish_time:.3f} 微秒")
    print()
    
    print("=" * 80)
    print("每节点平均发送带宽统计")
    print("=" * 80)
    print(f"{'节点ID':<10} {'流数量':<10} {'总字节数':<15} {'开始时间(μs)':<15} {'结束时间(μs)':<15} {'活跃时间(s)':<12} {'平均带宽(Gbps)':<20}")
    print("-" * 80)
    
    sorted_send = sorted(send_bandwidth.items())
    total_send_gbps = 0
    for node_id, info in sorted_send:
        print(f"{node_id:<10} {info['num_flows']:<10} {info['total_bytes']:<15} {info['start_time']:<15.3f} {info['finish_time']:<15.3f} {info['active_time']:<12.6f} {info['avg_gbps']:<20.6f}")
        total_send_gbps += info['avg_gbps']
    
    avg_send_gbps = total_send_gbps / len(send_bandwidth) if send_bandwidth else 0
    print("-" * 80)
    print(f"{'平均':<10} {'':<10} {'':<15} {'':<15} {'':<15} {'':<12} {avg_send_gbps:<20.6f}")
    print(f"{'总计':<10} {'':<10} {'':<15} {'':<15} {'':<15} {'':<12} {total_send_gbps:<20.6f}")
    print()
    
    print("=" * 80)
    print("每节点平均接收带宽统计")
    print("=" * 80)
    print(f"{'节点ID':<10} {'流数量':<10} {'总字节数':<15} {'开始时间(μs)':<15} {'结束时间(μs)':<15} {'活跃时间(s)':<12} {'平均带宽(Gbps)':<20}")
    print("-" * 80)
    
    sorted_recv = sorted(recv_bandwidth.items())
    total_recv_gbps = 0
    for node_id, info in sorted_recv:
        print(f"{node_id:<10} {info['num_flows']:<10} {info['total_bytes']:<15} {info['start_time']:<15.3f} {info['finish_time']:<15.3f} {info['active_time']:<12.6f} {info['avg_gbps']:<20.6f}")
        total_recv_gbps += info['avg_gbps']
    
    avg_recv_gbps = total_recv_gbps / len(recv_bandwidth) if recv_bandwidth else 0
    print("-" * 80)
    print(f"{'平均':<10} {'':<10} {'':<15} {'':<15} {'':<15} {'':<12} {avg_recv_gbps:<20.6f}")
    print(f"{'总计':<10} {'':<10} {'':<15} {'':<15} {'':<15} {'':<12} {total_recv_gbps:<20.6f}")
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
    print("- 平均带宽 = 节点总字节数 × 8 / 节点总活跃时间")
    print("- 节点总活跃时间 = 最后一个流完成时间 - 第一个流开始时间")
    print("- 这种方法考虑了流的并发性，反映了节点的实际带宽使用情况")

if __name__ == '__main__':
    main()