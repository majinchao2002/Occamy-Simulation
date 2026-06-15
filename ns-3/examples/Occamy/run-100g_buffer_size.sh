#!/usr/bin/env bash

set -euo pipefail

echo "hello, this experiment evaluates the impact of switch buffer size"

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR/../.."

SERVER_LEAF_CAP=100
nPrior=2
requestFlowRate=200.0
N_CORES=${N_CORES:-20}
N=0

running_sims() {
    pgrep -fc 'occamy_100g_benchmark-optimized' || true
}

method_array=("DT" "ABM" "PUSHOUT" "pBuffer")
tcpProtocol_array=("DCTCP")
webLoad_array=(0.4)
requestSizeRate_array=(0.4)
bufferPerPortPerGbps_array=(9.60 8.00 7.00 6.00 5.12 3.44)

for bufferPerPortPerGbps in "${bufferPerPortPerGbps_array[@]}"; do
    bufferSize=$(python3 -c "print(int(${bufferPerPortPerGbps}*1024*8*${SERVER_LEAF_CAP}))")
    for webLoad in "${webLoad_array[@]}"; do
        for requestSizeRate in "${requestSizeRate_array[@]}"; do
            for tcpProtocol in "${tcpProtocol_array[@]}"; do
                for method in "${method_array[@]}"; do
                    alpha=1.0
                    if [ "$method" = "pBuffer" ]; then
                        alpha=8.0
                    fi
                    if [ "$method" = "ABM" ]; then
                        alpha=2.0
                    fi

                    while [ "$(running_sims)" -gt "$N_CORES" ]; do
                        sleep 10
                        echo "waiting for cores, $N running..."
                    done

                    N=$((N + 1))
                    echo "./ns3 run \"examples/Occamy/occamy_100g_benchmark.cc --method=${method} --alpha=${alpha} --tcpProtocol=${tcpProtocol} --webLoad=${webLoad} --requestSizeRate=${requestSizeRate} --requestFlowRate=${requestFlowRate} --bufferSize=${bufferSize} --nPrior=${nPrior} --outDir=100g_buffer_size\" # ${bufferPerPortPerGbps}KB/port/Gbps"
                    ./ns3 run "examples/Occamy/occamy_100g_benchmark.cc --method=${method} --alpha=${alpha} --tcpProtocol=${tcpProtocol} --webLoad=${webLoad} --requestSizeRate=${requestSizeRate} --requestFlowRate=${requestFlowRate} --bufferSize=${bufferSize} --nPrior=${nPrior} --outDir=100g_buffer_size" > /dev/null &
                    sleep 2
                    echo "$N"
                done
            done
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
