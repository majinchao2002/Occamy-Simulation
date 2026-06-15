import os
import sys
import math
import numpy as np
import matplotlib.pyplot as plt
import xml.etree.ElementTree as etree


method_array = ["pBuffer-8.0", "Long-pBuffer-8.0"]
method_label = {"pBuffer-8.0": "RR head-drop (Occamy)", "Long-pBuffer-8.0": "Longest head-drop"}
tcp_protocol_array = ["DCTCP"]
web_load_array = ["0.4"]
request_size_rate_array = ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "1.0"]
request_flow_rate_array = ["200.0"]
buffer_size_array = ["4194304"]
queue_num_array = ["2"]
performance_parameter = [
    "query_QCT_ave",
    "query_QCT_99th",
    "web_FCT_ave",
    "small_web_FCT_99th",
    "query_QCT_ave_slowdown",
    "query_QCT_99th_slowdown",
    "web_FCT_ave_slowdown",
    "small_web_FCT_99th_slowdown",
]

data = {}
data_array = {}


def parse_one_xml(file_name):
    print(file_name)
    root = etree.parse(file_name).getroot()
    flow_stats = root[0]
    ipv4_flow_classifier = root[1]
    flow_dict = {}
    for child in ipv4_flow_classifier:
        flow_id = child.attrib["flowId"]
        src_ip = child.attrib["sourceAddress"]
        dst_ip = child.attrib["destinationAddress"]
        protocol = child.attrib["protocol"]
        src_port = child.attrib["sourcePort"]
        dst_port = child.attrib["destinationPort"]
        flow_key = (src_ip, dst_ip, src_port, dst_port, protocol)

        index = int(flow_id) - 1
        flow_stats_attr = flow_stats[index].attrib
        start_time = float(flow_stats_attr["timeFirstTxPacket"].replace("+", "").replace("ns", ""))
        stop_time = float(flow_stats_attr["timeLastRxPacket"].replace("+", "").replace("ns", ""))
        loss_packets = int(flow_stats_attr["lostPackets"])
        receive_packets = int(flow_stats_attr["rxPackets"])
        receive_bytes = int(flow_stats_attr["rxBytes"])

        complete_time = stop_time - start_time
        base_rtt = 2.0 * 40 / 1000000
        slowdown = complete_time / 1000000000 / (base_rtt * 2 + receive_bytes * 8.0 / 100000000000)

        flow_dict[flow_key] = {
            "startTime": start_time,
            "completeTime": complete_time,
            "isPositive": "UDP",
            "lostPackets": loss_packets,
            "rxPackets": receive_packets,
            "rxBytes": receive_bytes,
            "flowid": int(flow_id),
            "fctSlowdown": slowdown,
        }

        opposite_flow_key = (dst_ip, src_ip, dst_port, src_port, protocol)
        if opposite_flow_key in flow_dict:
            if flow_dict[flow_key]["flowid"] < flow_dict[opposite_flow_key]["flowid"]:
                flow_dict[flow_key]["isPositive"] = "TCP-TRUE"
                flow_dict[opposite_flow_key]["isPositive"] = "TCP-FALSE"
            else:
                flow_dict[flow_key]["isPositive"] = "TCP-FALSE"
                flow_dict[opposite_flow_key]["isPositive"] = "TCP-TRUE"

    ans = {}

    # query (burst) flows: dst_port >= 20010
    QCT = {}
    QCT_bytes = {}
    for flow_key, flow_value in flow_dict.items():
        dst_port = int(flow_key[3])
        dst_ip = flow_key[1]
        if flow_value["isPositive"] == "TCP-TRUE" and dst_port >= 20010:
            qct_key = (dst_ip, flow_value["startTime"])
            QCT[qct_key] = max(QCT.get(qct_key, 0), flow_value["completeTime"])
            QCT_bytes[qct_key] = QCT_bytes.get(qct_key, 0) + flow_value["rxBytes"]

    QCT_list = sorted(QCT.values())
    QCT_slowdown_list = sorted(
        v / 1000000000 / (2.0 * 40 / 1000000 * 2 + QCT_bytes[k] * 8.0 / 100000000000)
        for k, v in QCT.items()
    )
    if QCT_list:
        idx99 = math.ceil(len(QCT_list) / 100 * 99) - 1
        ans["query_QCT_ave"] = float(np.mean(QCT_list))
        ans["query_QCT_99th"] = QCT_list[idx99]
        ans["query_QCT_ave_slowdown"] = float(np.mean(QCT_slowdown_list))
        ans["query_QCT_99th_slowdown"] = QCT_slowdown_list[idx99]
    else:
        ans["query_QCT_ave"] = 0
        ans["query_QCT_99th"] = 0
        ans["query_QCT_ave_slowdown"] = 0
        ans["query_QCT_99th_slowdown"] = 0

    # web flows: dst_port < 20010
    web_FCT = []
    web_FCT_slow = []
    for flow_key, flow_value in flow_dict.items():
        dst_port = int(flow_key[3])
        if flow_value["isPositive"] == "TCP-TRUE" and dst_port < 20010:
            web_FCT.append(flow_value["completeTime"])
            web_FCT_slow.append(flow_value["fctSlowdown"])
    web_FCT.sort()
    web_FCT_slow.sort()
    if web_FCT:
        ans["web_FCT_ave"] = float(np.mean(web_FCT))
        ans["web_FCT_ave_slowdown"] = float(np.mean(web_FCT_slow))
    else:
        ans["web_FCT_ave"] = 0
        ans["web_FCT_ave_slowdown"] = 0

    # small web flows: dst_port < 20010 and rxBytes <= 100000
    small_web_FCT = []
    small_web_FCT_slow = []
    for flow_key, flow_value in flow_dict.items():
        dst_port = int(flow_key[3])
        if (
            flow_value["isPositive"] == "TCP-TRUE"
            and dst_port < 20010
            and flow_value["rxBytes"] <= 100000
        ):
            small_web_FCT.append(flow_value["completeTime"])
            small_web_FCT_slow.append(flow_value["fctSlowdown"])
    small_web_FCT.sort()
    small_web_FCT_slow.sort()
    if small_web_FCT:
        idx99 = math.ceil(len(small_web_FCT) / 100 * 99) - 1
        ans["small_web_FCT_99th"] = small_web_FCT[idx99]
        ans["small_web_FCT_99th_slowdown"] = small_web_FCT_slow[idx99]
    else:
        ans["small_web_FCT_99th"] = 0
        ans["small_web_FCT_99th_slowdown"] = 0

    return ans


def collect(file_dir, output_file):
    rows = []
    for root, dirs, files in os.walk(file_dir):
        for fn in sorted(files):
            if not fn.endswith(".xml"):
                continue
            key = fn.replace(".xml", "")
            method = key.split("~")[0]
            if method not in method_array:
                continue
            ans = parse_one_xml(os.path.join(root, fn))
            data[key] = ans
            line = key + " " + " ".join(str(ans[p]) for p in performance_parameter)
            rows.append(line)
    with open(output_file, "w") as f:
        f.write("\n".join(rows) + "\n")


def index_data():
    for key, value in data.items():
        method = key.split("~")[0]
        parameter = key.split("~")[1].split("-")
        tcp_protocol = parameter[0]
        web_load = parameter[1]
        request_size_rate = parameter[2]
        request_flow_rate = parameter[3]
        buffer_size = parameter[4]
        queue_num = parameter[5]
        data_array[(method, tcp_protocol, web_load, request_size_rate, request_flow_rate, buffer_size, queue_num)] = value


def draw(folder_name):
    for tcp_protocol in tcp_protocol_array:
        for web_load in web_load_array:
            for request_flow_rate in request_flow_rate_array:
                for buffer_size in buffer_size_array:
                    for queue_num in queue_num_array:
                        for performance in performance_parameter:
                            plt.figure()
                            for method in method_array:
                                x, y = [], []
                                for rsr in request_size_rate_array:
                                    key = (method, tcp_protocol, web_load, rsr, request_flow_rate, buffer_size, queue_num)
                                    if key not in data_array:
                                        continue
                                    x.append(float(rsr))
                                    y.append(float(data_array[key][performance]))
                                plt.plot(x, y, marker="o", linewidth=1.5, label=method_label[method])
                            plt.xlabel("Request Size Rate", fontsize=12)
                            plt.ylabel(performance, fontsize=12)
                            plt.ylim(bottom=0)
                            plt.legend(loc="best", fontsize=10)
                            figure_name = (
                                f"{performance}-{tcp_protocol}-{web_load}-XX-"
                                f"{request_flow_rate}-{buffer_size}-{queue_num}"
                            )
                            plt.title(figure_name, fontsize=13)
                            plt.grid(True, linestyle="--", linewidth=0.5)
                            plt.tight_layout()
                            out = os.path.join(folder_name, figure_name + ".jpg")
                            print(out)
                            plt.savefig(out, dpi=300)
                            plt.close()


def report_gap():
    """Print average percentage gap between RR and Longest for headline metrics."""
    headline = ["query_QCT_ave", "web_FCT_ave"]
    for tcp_protocol in tcp_protocol_array:
        for web_load in web_load_array:
            for request_flow_rate in request_flow_rate_array:
                for buffer_size in buffer_size_array:
                    for queue_num in queue_num_array:
                        for performance in headline:
                            diffs = []
                            for rsr in request_size_rate_array:
                                rr_key = ("pBuffer-8.0", tcp_protocol, web_load, rsr, request_flow_rate, buffer_size, queue_num)
                                lg_key = ("Long-pBuffer-8.0", tcp_protocol, web_load, rsr, request_flow_rate, buffer_size, queue_num)
                                if rr_key not in data_array or lg_key not in data_array:
                                    continue
                                rr = data_array[rr_key][performance]
                                lg = data_array[lg_key][performance]
                                if lg == 0:
                                    continue
                                diffs.append(abs(rr - lg) / lg * 100)
                            if diffs:
                                print(f"[{performance}] webLoad={web_load} avg |RR-Long|/Long = {np.mean(diffs):.2f}%  max = {np.max(diffs):.2f}%")


if __name__ == "__main__":
    file_dir = "100g_head_drop/"
    data_output_file = "data/100g_head_drop.txt"
    figure_output_folder = "figure/100g_head_drop/"

    os.makedirs(os.path.dirname(data_output_file), exist_ok=True)
    os.makedirs(figure_output_folder, exist_ok=True)

    collect(file_dir, data_output_file)
    index_data()
    draw(figure_output_folder)
    report_gap()
