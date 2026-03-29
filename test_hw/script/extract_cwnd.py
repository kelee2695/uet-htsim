#!/usr/bin/env python3
import sys
import argparse

def extract_cwnd_lines(input_file, output_file):
    try:
        with open(input_file, 'r') as infile:
            lines = infile.readlines()
        
        cwnd_lines = []
        for line in lines:
            if 'cwnd' in line.lower():
                cwnd_lines.append(line.rstrip('\n'))
        
        with open(output_file, 'w') as outfile:
            for line in cwnd_lines:
                outfile.write(line + '\n')
        
        print(f"成功提取 {len(cwnd_lines)} 行包含cwnd的数据")
        print(f"结果已保存到: {output_file}")
        
        if cwnd_lines:
            print(f"\n=== 前5行示例 ===")
            for i, line in enumerate(cwnd_lines[:5]):
                print(f"{i+1}. {line}")
    
    except FileNotFoundError:
        print(f"错误: 找不到输入文件 {input_file}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='提取所有包含cwnd的行')
    parser.add_argument('-i', '--input', required=True, help='输入文件路径')
    parser.add_argument('-o', '--output', required=True, help='输出文件路径')
    
    args = parser.parse_args()
    
    extract_cwnd_lines(args.input, args.output)

if __name__ == "__main__":
    main()
