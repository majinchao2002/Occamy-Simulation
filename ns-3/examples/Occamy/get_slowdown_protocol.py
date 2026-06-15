import csv
import math
import os
import xml.etree.ElementTree as etree

import matplotlib.pyplot as plt
import numpy as np


data = {}
data_array = {}
method_array = ["DT-1.0", "PUSHOUT-1.0", "ABM-2.0", "pBuffer-8.0"]
method_label = {
    "DT-1.0": "DT",
    "PUSHOUT-1.0": "Pushout",
    "ABM-2.0": "ABM",
    "pBuffer-8.0": "Occamy",
}
tcp_protocol_array = ["TIMELY", "HPCC", "THETAPOWERTCP"]
queue_num_array = ["2"]
buffer_size_array = ["4194304"]
request_flow_rate_array = ["200.0"]
request_size_rate_array = ["0.4"]
web_load_array = ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9"]
performance_parameter = [
    "query_QCT_ave_slowdown",
    "query_QCT_99th_slowdown",
    "web_FCT_ave_slowdown",
    "web_FCT_99th_slowdown",
]


def percentile(values, pct):
    if not values:
        return 0
    idx = math.ceil(len(values) / 100 * pct) - 1
    return values[max(0, min(idx, len(values) - 1))]


def parse_one_xml(file_name):
    print(file_name)
    root = etree.parse(file_name).getroot()
    flow_stats = root[0]
    ipv4_flow_classifier = root[1]
    flow_dict = {}

    for child in ipv4_flow_classifier:
        flow_id = child.attrib["flowId"]
        flow_key = (
            child.attrib["sourceAddress"],
            child.attrib["destinationAddress"],
            child.attrib["sourcePort"],
            child.attrib["destinationPort"],
            child.attrib["protocol"],
        )
        attrs = flow_stats[int(flow_id) - 1].attrib
        start_time = float(attrs["timeFirstTxPacket"].replace("+", "").replace("ns", ""))
        stop_time = float(attrs["timeLastRxPacket"].replace("+", "").replace("ns", ""))
        receive_bytes = int(attrs["rxBytes"])
        complete_time = stop_time - start_time
        base_rtt = 2.0 * 40 / 1000000
        slowdown = complete_time / 1000000000 / (base_rtt * 2 + receive_bytes * 8.0 / 100000000000)

        flow_dict[flow_key] = {
            "startTime": start_time,
            "completeTime": complete_time,
            "isPositive": "UDP",
            "rxBytes": receive_bytes,
            "flowid": int(flow_id),
            "fctSlowdown": slowdown,
        }

        opposite_flow_key = (flow_key[1], flow_key[0], flow_key[3], flow_key[2], flow_key[4])
        if opposite_flow_key in flow_dict:
            if flow_dict[flow_key]["flowid"] < flow_dict[opposite_flow_key]["flowid"]:
                flow_dict[flow_key]["isPositive"] = "TCP-TRUE"
                flow_dict[opposite_flow_key]["isPositive"] = "TCP-FALSE"
            else:
                flow_dict[flow_key]["isPositive"] = "TCP-FALSE"
                flow_dict[opposite_flow_key]["isPositive"] = "TCP-TRUE"

    qct = {}
    qct_bytes = {}
    web_fct_slowdown = []

    for flow_key, flow_value in flow_dict.items():
        if flow_value["isPositive"] != "TCP-TRUE":
            continue
        dst_port = int(flow_key[3])
        if dst_port >= 20010:
            qct_key = (flow_key[1], flow_value["startTime"])
            qct[qct_key] = max(qct.get(qct_key, 0), flow_value["completeTime"])
            qct_bytes[qct_key] = qct_bytes.get(qct_key, 0) + flow_value["rxBytes"]
        else:
            web_fct_slowdown.append(flow_value["fctSlowdown"])

    qct_slowdown = sorted(
        v / 1000000000 / (2.0 * 40 / 1000000 * 2 + qct_bytes[k] * 8.0 / 100000000000)
        for k, v in qct.items()
    )
    web_fct_slowdown.sort()

    return {
        "query_QCT_ave_slowdown": float(np.mean(qct_slowdown)) if qct_slowdown else 0,
        "query_QCT_99th_slowdown": percentile(qct_slowdown, 99),
        "web_FCT_ave_slowdown": float(np.mean(web_fct_slowdown)) if web_fct_slowdown else 0,
        "web_FCT_99th_slowdown": percentile(web_fct_slowdown, 99),
    }


def parse_key(key):
    method, parameter = key.split("~")
    tcp_protocol, web_load, request_size_rate, request_flow_rate, buffer_size, queue_num = parameter.split("-")
    return method, tcp_protocol, web_load, request_size_rate, request_flow_rate, buffer_size, queue_num


def collect(file_dir, output_file):
    rows = []
    for root, _, files in os.walk(file_dir):
        for fn in sorted(files):
            if not fn.endswith(".xml"):
                continue
            key = fn.replace(".xml", "")
            parsed = parse_key(key)
            method, tcp_protocol, web_load, request_size_rate, request_flow_rate, buffer_size, queue_num = parsed
            if method not in method_array or tcp_protocol not in tcp_protocol_array:
                continue
            if web_load not in web_load_array or request_size_rate not in request_size_rate_array:
                continue
            if request_flow_rate not in request_flow_rate_array or buffer_size not in buffer_size_array:
                continue
            if queue_num not in queue_num_array:
                continue

            ans = parse_one_xml(os.path.join(root, fn))
            data[key] = ans
            data_array[parsed] = ans
            rows.append([key] + [ans[p] for p in performance_parameter])

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["key"] + performance_parameter)
        writer.writerows(rows)


def draw(folder_name):
    os.makedirs(folder_name, exist_ok=True)
    for tcp_protocol in tcp_protocol_array:
        for metric in performance_parameter:
            plt.figure()
            for method in method_array:
                x, y = [], []
                for web_load in web_load_array:
                    key = (method, tcp_protocol, web_load, "0.4", "200.0", "4194304", "2")
                    if key not in data_array:
                        continue
                    x.append(float(web_load))
                    y.append(data_array[key][metric])
                if x:
                    plt.plot(x, y, marker="o", linewidth=1.5, label=method_label[method])
            plt.xlabel("Web Load", fontsize=12)
            plt.ylabel(metric, fontsize=12)
            plt.ylim(bottom=0)
            plt.legend(loc="best", fontsize=10)
            plt.grid(True, linestyle="--", linewidth=0.5)
            plt.tight_layout()
            out = os.path.join(folder_name, f"{metric}-{tcp_protocol}-webload.jpg")
            print(out)
            plt.savefig(out, dpi=300)
            plt.close()


if __name__ == "__main__":
    file_dir = "100g_protocol/"
    data_output_file = "data/100g_protocol.csv"
    figure_output_folder = "figure/100g_protocol/"

    collect(file_dir, data_output_file)
    draw(figure_output_folder)
