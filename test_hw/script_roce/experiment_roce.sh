#!/bin/bash

BASE_DIR="/home/lrh/uet-htsim/test_hw/2spine_4leaf_256"
RESULT_DIR="${BASE_DIR}/result_roce"
SCRIPT_DIR="/home/lrh/uet-htsim/test_hw/script_roce"
MAX_CONCURRENT=${2:-4}

RED='\033[0;31m' GREEN='\033[0;32m' BLUE='\033[0;34m' NC='\033[0m'
msg() { echo -e "${GREEN}✓${NC} $1"; }
err() { echo -e "${RED}✗${NC} $1"; }
inf() { echo -e "${BLUE}ℹ${NC} $1"; }

[[ $# -eq 0 ]] && { echo "用法: $0 <实验组文件> [并发数]"; ls "${BASE_DIR}"/experiment_group_roce*.json 2>/dev/null | xargs -n1 basename; exit 1; }

EXPERIMENT_GROUP="${BASE_DIR}/$1"
[[ ! -f "$EXPERIMENT_GROUP" ]] && { err "文件不存在: $EXPERIMENT_GROUP"; exit 1; }

EXPERIMENT_RESULT_DIR="${RESULT_DIR}_$(basename "$EXPERIMENT_GROUP" .json | sed 's/^experiment_group_//')"
mkdir -p "$EXPERIMENT_RESULT_DIR"

echo -e "${BLUE}并发: ${MAX_CONCURRENT} | 实验组: $(basename "$EXPERIMENT_GROUP") | 结果: ${EXPERIMENT_RESULT_DIR}${NC}\n"

STATUS_FILE="/tmp/exp_status_$$.txt"
PIDS_FILE="/tmp/exp_pids_$$.txt"
EXPS_FILE="/tmp/exps_$$.txt"
> "$STATUS_FILE" > "$PIDS_FILE"

python3 -c "
import json
with open('${EXPERIMENT_GROUP}') as f:
    for exp in json.load(f).get('experiments', []):
        cmd = exp['command'] + ' ' + ' '.join(exp['args'])
        if exp.get('log'): cmd += ' -o ' + exp['log']
        print(f\"{exp['name']}|{cmd}|{exp['output']}|{exp.get('log','')}\")
" > "$EXPS_FILE"

run_one() {
    local name=$1 cmd=$2 result=$3 logf=$4 dir="${EXPERIMENT_RESULT_DIR}/${name}"
    mkdir -p "$dir"
    if eval "$cmd > \"$result\" 2>&1" && [[ -f "$result" ]]; then
        mv "$result" "$dir/result.txt"
        [[ -f "$logf" ]] && mv "$logf" "$dir/result.log"
        python3 "$SCRIPT_DIR/analyze_fct.py" -i "$dir/result.txt" -o "$dir" >/dev/null 2>&1
        echo "S:$name" >> "$STATUS_FILE"
    else
        echo "F:$name" >> "$STATUS_FILE"
    fi
}

while IFS='|' read -r name cmd result logf; do
    while [[ $(wc -l < "$PIDS_FILE") -ge $MAX_CONCURRENT ]]; do
        sleep 1
        sed -i '/^$/d' "$PIDS_FILE"
        for pid in $(cat "$PIDS_FILE"); do kill -0 $pid 2>/dev/null || sed -i "/^$pid$/d" "$PIDS_FILE"; done
    done
    run_one "$name" "$cmd" "$result" "$logf" &
    echo $! >> "$PIDS_FILE"
    inf "实验 $name 已启动"
done < "$EXPS_FILE"

rm -f "$EXPS_FILE"
inf "等待实验完成..."
while [[ -s "$PIDS_FILE" ]]; do sleep 1; for pid in $(cat "$PIDS_FILE"); do kill -0 $pid 2>/dev/null || sed -i "/^$pid$/d" "$PIDS_FILE"; done; done
rm -f "$PIDS_FILE"

msg "所有实验已完成"

if [[ -s "$STATUS_FILE" ]]; then
    python3 "$SCRIPT_DIR/analyze_fct.py" -d "$EXPERIMENT_RESULT_DIR" -o "${EXPERIMENT_RESULT_DIR}/figures" 2>/dev/null
    msg "FCT分析完成"
fi

rm -f "$STATUS_FILE"
exit 0
