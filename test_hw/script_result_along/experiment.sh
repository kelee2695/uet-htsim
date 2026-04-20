#!/bin/bash

BASE_DIR="/home/lrh/uet-htsim/test_hw/2spine_4leaf_256"
RESULT_DIR="${BASE_DIR}/result"
SCRIPT_DIR="/home/lrh/uet-htsim/test_hw/script_result_along"
PARSE_OUTPUT="/home/lrh/uet-htsim/htsim/sim/build/parse_output"
MAX_CONCURRENT=${2:-6}

RED='\033[0;31m' GREEN='\033[0;32m' BLUE='\033[0;34m' NC='\033[0m'
msg() { echo -e "${GREEN}✓${NC} $1"; }
err() { echo -e "${RED}✗${NC} $1"; }
inf() { echo -e "${BLUE}ℹ${NC} $1"; }

[[ $# -eq 0 ]] && { echo "用法: $0 <实验组文件> [并发数]"; ls "${BASE_DIR}"/experiment_group_*.json 2>/dev/null | xargs -n1 basename; exit 1; }

EXPERIMENT_GROUP="${BASE_DIR}/$1"
[[ ! -f "$EXPERIMENT_GROUP" ]] && { err "文件不存在: $EXPERIMENT_GROUP"; exit 1; }

EXPERIMENT_RESULT_DIR="${RESULT_DIR}_$(basename "$EXPERIMENT_GROUP" .json | sed 's/^experiment_group_//')"
[[ ! -d "$EXPERIMENT_RESULT_DIR" ]] && { err "结果目录不存在: $EXPERIMENT_RESULT_DIR"; exit 1; }

echo -e "${BLUE}并发: ${MAX_CONCURRENT} | 实验组: $(basename "$EXPERIMENT_GROUP") | 结果目录: ${EXPERIMENT_RESULT_DIR}${NC}\n"

STATUS_FILE="/tmp/exp_status_$$.txt"
PIDS_FILE="/tmp/exp_pids_$$.txt"
EXPS_FILE="/tmp/exps_$$.txt"
> "$STATUS_FILE" > "$PIDS_FILE"

python3 -c "
import json
with open('${EXPERIMENT_GROUP}') as f:
    for exp in json.load(f).get('experiments', []):
        print(f\"{exp['name']}|{exp.get('log','')}\")
" > "$EXPS_FILE"

analyze_one() {
    local name=$1 logf=$2 dir="${EXPERIMENT_RESULT_DIR}/${name}"
    
    if [[ ! -d "$dir" ]]; then
        err "实验目录不存在: $dir"
        echo "F:$name" >> "$STATUS_FILE"
        return
    fi
    
    if [[ ! -f "$dir/result.txt" ]]; then
        err "结果文件不存在: $dir/result.txt"
        echo "F:$name" >> "$STATUS_FILE"
        return
    fi
    
    inf "正在分析: $name"
    
    # 如果存在 result.log 但不存在 result_parsed.log，则解析
    if [[ -f "$dir/result.log" ]] && [[ ! -f "$dir/result_parsed.log" ]]; then
        "$PARSE_OUTPUT" "$dir/result.log" -ascii > "$dir/result_parsed.log" 2>&1
    fi
    
    # 提取流映射（每次更新）
    python3 "$SCRIPT_DIR/extract_flow_mapping.py" -i "$dir/result.txt" -o "$dir/cwnd_flow_map.txt" >/dev/null 2>&1
    
    # 分析拥塞窗口（每次更新）
    python3 "$SCRIPT_DIR/analyze_cwnd.py" -i "$dir/result.txt" -m "$dir/cwnd_flow_map.txt" -o "$dir/cwnd_change.csv" -e "$dir/cwnd_events.txt" >/dev/null 2>&1
    
    # 绘制拥塞窗口图（每次更新）
    python3 "$SCRIPT_DIR/plot_cwnd.py" -i "$dir/cwnd_change.csv" -o "$dir/cwnd_plot.png" -n 5 >/dev/null 2>&1
    
    # 分析发送速率（每次更新）
    python3 "$SCRIPT_DIR/analyze_send_rate.py" -i "$dir/result.txt" -o "$dir/send_rate_per_flow.csv" -n "$dir/send_rate_per_node.csv" >/dev/null 2>&1
    
    # 分析接收速率（每次更新）
    if [[ -f "$dir/result_parsed.log" ]]; then
        python3 "$SCRIPT_DIR/analyze_receive_rate.py" -i "$dir/result_parsed.log" -o "$dir/receive_rate.csv" >/dev/null 2>&1
    fi
    
    # 数据包在网时延统计（每次更新）
    if [[ -f "$dir/cwnd_flow_map.txt" ]]; then
        python3 "$SCRIPT_DIR/analyze_network_delay.py" "$dir/result.txt" "$dir/cwnd_flow_map.txt" "$dir/network_delay_stats.csv" >/dev/null 2>&1
    fi
    
    echo "S:$name" >> "$STATUS_FILE"
    msg "分析完成: $name"
}

run_analysis() {
    echo "生成队列分析报告..."
    python3 "$SCRIPT_DIR/analyze_queues.py" -i "$EXPERIMENT_RESULT_DIR" >/dev/null 2>&1
    
    # 为每个实验生成队列深度阈值统计
    echo "生成队列深度阈值统计..."
    for exp_dir in "$EXPERIMENT_RESULT_DIR"/*/; do
        if [[ -f "$exp_dir/queue_depth.csv" ]]; then
            python3 "/home/lrh/uet-htsim/test_hw/script/count_threshold.py" \
                -i "$exp_dir/queue_depth.csv" \
                -o "$exp_dir/queue_depth_threshold.csv" \
                -t 1245000 >/dev/null 2>&1
        fi
    done
}

while IFS='|' read -r name logf; do
    while [[ $(wc -l < "$PIDS_FILE") -ge $MAX_CONCURRENT ]]; do
        sleep 0.5
        sed -i '/^$/d' "$PIDS_FILE"
        for pid in $(cat "$PIDS_FILE"); do kill -0 $pid 2>/dev/null || sed -i "/^$pid$/d" "$PIDS_FILE"; done
    done
    analyze_one "$name" "$logf" &
    echo $! >> "$PIDS_FILE"
done < "$EXPS_FILE"

rm -f "$EXPS_FILE"
inf "等待分析完成..."
while [[ -s "$PIDS_FILE" ]]; do sleep 0.5; for pid in $(cat "$PIDS_FILE"); do kill -0 $pid 2>/dev/null || sed -i "/^$pid$/d" "$PIDS_FILE"; done; done
rm -f "$PIDS_FILE"

msg "所有实验分析已完成"

[[ -s "$STATUS_FILE" ]] && python3 "$SCRIPT_DIR/analyze_experiments.py" "$EXPERIMENT_RESULT_DIR" "${EXPERIMENT_RESULT_DIR}/概要" 2>/dev/null && msg "整体分析完成"

run_analysis

rm -f "$STATUS_FILE"
exit 0