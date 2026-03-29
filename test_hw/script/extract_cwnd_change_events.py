#!/usr/bin/env python3
import sys
import argparse
import re

def extract_cwnd_change_events(input_file, output_file):
    try:
        with open(input_file, 'r') as infile:
            lines = infile.readlines()
        
        fulfill_adjustment_lines = []
        
        for line in lines:
            if 'fulfill_adjustment' in line or 'Running fulfill adjustment' in line:
                fulfill_adjustment_lines.append(line.strip())
        
        with open(output_file, 'w') as outfile:
            for line in fulfill_adjustment_lines:
                outfile.write(line + '\n')
        
        print(f"成功提取 {len(fulfill_adjustment_lines)} 行fulfill_adjustment信息")
        print(f"结果已保存到: {output_file}")
        
        if fulfill_adjustment_lines:
            print(f"\n=== 信息类型统计 ===")
            fulfill_adjustmentx_count = sum(1 for line in fulfill_adjustment_lines if 'fulfill_adjustmentx' in line)
            running_adjustment_count = sum(1 for line in fulfill_adjustment_lines if 'Running fulfill adjustment' in line)
            fulfill_adjustment_count = sum(1 for line in fulfill_adjustment_lines if 'fulfill_adjustment ' in line and 'fulfill_adjustmentx' not in line and 'Running fulfill adjustment' not in line)
              
            print(f"fulfill_adjustmentx (调整前): {fulfill_adjustmentx_count} 行")
            print(f"Running fulfill adjustment (详细调整): {running_adjustment_count} 行")
            print(f"fulfill_adjustment (调整后): {fulfill_adjustment_count} 行")
              
            print(f"\n=== 前10行示例 ===")
            for i, line in enumerate(fulfill_adjustment_lines[:10]):
                print(f"{i+1}. {line}")
    
    except FileNotFoundError:
        print(f"错误: 找不到输入文件 {input_file}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='提取cwnd变化事件信息')
    parser.add_argument('-i', '--input', required=True, help='输入文件路径')
    parser.add_argument('-o', '--output', required=True, help='输出文件路径')
    
    args = parser.parse_args()
    
    extract_cwnd_change_events(args.input, args.output)