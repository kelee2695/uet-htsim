#!/usr/bin/env python3
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_cwnd_curves(input_file, output_dir):
    try:
        df = pd.read_csv(input_file)
        
        df_uename = df[~df['flow'].str.match(r'^\d+$')].copy()
        
        unique_flows = df_uename['flow'].unique()
        
        cwnd_output_dir = os.path.join(output_dir, 'cwnd')
        if not os.path.exists(cwnd_output_dir):
            os.makedirs(cwnd_output_dir)
        
        for flow in unique_flows:
            flow_data = df_uename[df_uename['flow'] == flow]
            
            plt.figure(figsize=(12, 6))
            plt.plot(flow_data['time'], flow_data['cwnd'], 
                    color='blue', linewidth=2, alpha=0.8)
            
            plt.xlabel('Time (μs)', fontsize=12)
            plt.ylabel('CWND (bytes)', fontsize=12)
            plt.title(f'CWND vs Time - Flow {flow}', fontsize=14, fontweight='bold')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            safe_flow_name = flow.replace('/', '_').replace('\\', '_')
            output_path = os.path.join(cwnd_output_dir, f'cwnd_{safe_flow_name}.png')
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
        
        print(f"Total plots created: {len(unique_flows)}")
        print(f"Output directory: {cwnd_output_dir}")
        print(f"Time range: {df_uename['time'].min():.2f} - {df_uename['time'].max():.2f} μs")
        print(f"CWND range: {df_uename['cwnd'].min():.0f} - {df_uename['cwnd'].max():.0f} bytes")
    
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Plot individual CWND vs time curves from CSV data')
    parser.add_argument('-i', '--input', required=True, help='Input CSV file path')
    parser.add_argument('-o', '--output', required=True, help='Output directory path')
    
    args = parser.parse_args()
    
    plot_cwnd_curves(args.input, args.output)