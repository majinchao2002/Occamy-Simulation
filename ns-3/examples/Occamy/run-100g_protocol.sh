#!/usr/bin/env bash

set -euo pipefail

echo "hello, this experiment evaluates protocol comparison across web loads"

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR/../.."

SERVER_LEAF_CAP=100
BUFFER_PER_PORT_PER_GBPS=5.12
nPrior=2
requestFlowRate=200.0
requestSizeRate=0.4
bufferSize=$(python3 -c "print(int(${BUFFER_PER_PORT_PER_GBPS}*1024*8*${SERVER_LEAF_CAP}))")
N_CORES=${N_CORES:-20}
N=0

running_sims() {
    pgrep -fc 'occamy_100g_benchmark-optimized' || true
}

method_alpha_array=("DT:1.0" "PUSHOUT:1.0" "ABM:2.0" "pBuffer:8.0")
tcpProtocol_array=("TIMELY" "HPCC" "THETAPOWERTCP")
webLoad_array=(0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9)

for webLoad in "${webLoad_array[@]}"; do
    for tcpProtocol in "${tcpProtocol_array[@]}"; do
        for methodAlpha in "${method_alpha_array[@]}"; do
            method=${methodAlpha%%:*}
            alpha=${methodAlpha##*:}

            while [ "$(running_sims)" -gt "$N_CORES" ]; do
                sleep 10
                echo "waiting for cores, $N running..."
            done

            N=$((N + 1))
            echo "./ns3 run \"examples/Occamy/occamy_100g_benchmark.cc --method=${method} --alpha=${alpha} --tcpProtocol=${tcpProtocol} --webLoad=${webLoad} --requestSizeRate=${requestSizeRate} --requestFlowRate=${requestFlowRate} --bufferSize=${bufferSize} --nPrior=${nPrior} --outDir=100g_protocol\""
            ./ns3 run "examples/Occamy/occamy_100g_benchmark.cc --method=${method} --alpha=${alpha} --tcpProtocol=${tcpProtocol} --webLoad=${webLoad} --requestSizeRate=${requestSizeRate} --requestFlowRate=${requestFlowRate} --bufferSize=${bufferSize} --nPrior=${nPrior} --outDir=100g_protocol" > /dev/null &
            sleep 2
            echo "$N"
        done
    done
done

while [ "$(running_sims)" -gt 0 ]; do
    echo "Waiting for simulations to finish..."
    sleep 5
done

echo "##################################"
echo "#      FINISHED EXPERIMENTS      #"
echo "##################################"
