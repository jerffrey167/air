import requests
import pandas as pd
import time
import os
from tqdm import tqdm

# --------------------------
# 程序配置区 - 可在此修改参数
# --------------------------
# 第二个接口的查询时间范围
START_TIME = "2025-07-01 00:00:00"  # 开始时间
END_TIME = "2025-08-17 20:00:00"  # 结束时间

# 输出文件路径
statistics_file = "空调设备统计数据-202508151920.xlsx"

# 请求间隔时间（秒）
request_delay = 0.4

# 第二个接口每页请求数量
page_size = 100

# --------------------------
# 通用配置 - 完整请求头
# --------------------------
headers = {
    "accept": "application/json, text/plain, */*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "zh-CN,zh;q=0.9",
    "authorization": "Bearer 67a91d9b-a23a-4587-a095-ddd3b9ff974a",
    "content-type": "application/json",
    "cookie": "token=67a91d9b-a23a-4587-a095-ddd3b9ff974a; refresh_token=2c6059fa-3b7e-422d-9ffd-a237e8330f5e; SESSION=YzVlNmVhYzktZWY0MS00ZDFlLTk0YzMtOTE5M2MyOGQ5ZDYz"
}

# 显示当前工作目录和配置信息
print("当前工作目录：", os.getcwd())
print(f"第二个接口查询时间范围：{START_TIME} 至 {END_TIME}\n")


# --------------------------
# 1. 处理第一个接口 - 获取设备基础信息
# --------------------------
def get_device_info():
    url = "https://air.tianruixinchengyun.com/api/airConditioner/listpages"

    # 设置较大的pageSize减少请求次数
    payload = {
        "page": 1,
        "pageSize": 1000,
        "sorts": [],
        "companyId": 844,
        "todayFlag": False
    }

    all_devices = []
    try:
        # 首次请求获取总页数
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        first_data = response.json()

        if first_data.get("code") == 0:
            # 修复：使用更安全的键访问方式
            data = first_data.get("data", {})
            total_pages = data.get("pageCount", 1)
            items = data.get("items", [])

            # 处理第一页的数据
            for item in items:
                all_devices.append(extract_device_info(item))

            # 如果有更多页，继续获取
            if total_pages > 1:
                print(f"第一个接口共{total_pages}页数据，开始获取...")
                # 使用tqdm添加进度条，从第2页开始
                for page in tqdm(range(2, total_pages + 1), desc="获取设备信息"):
                    payload["page"] = page
                    page_response = requests.post(url, json=payload, headers=headers)
                    page_response.raise_for_status()
                    page_data = page_response.json()

                    if page_data.get("code") == 0:
                        page_items = page_data.get("data", {}).get("items", [])
                        for item in page_items:
                            all_devices.append(extract_device_info(item))
                    else:
                        print(f"获取第{page}页数据失败：{page_data.get('message')}")

                    time.sleep(request_delay)

            print(f"\n第一个接口数据提取完成，共{len(all_devices)}条记录\n")
            return all_devices

        else:
            print(f"首次请求失败：{first_data.get('message')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"请求发生错误：{e}")
        return None


# 提取设备信息（合并楼宇和房间号）
def extract_device_info(item):
    # 合并楼宇名称和房间号
    building = item.get("buildingName", "")
    room = item.get("houseName", "")

    # 处理合并逻辑
    if building and room:
        location = f"{building}-{room}"
    elif building:
        location = building
    elif room:
        location = room
    else:
        location = ""

    return {
        "设备id": item.get("id", ""),
        "设备编号": item.get("serialNumber", ""),
        "位置": location,  # 合并后的位置信息
        "buildingId": item.get("buildingId", "")
    }


# --------------------------
# 2. 处理第二个接口 - 修复404错误
# --------------------------
def get_device_statistics(device_list):
    # 修复后的接口URL - 根据您的描述可能是URL变更导致的404
    url = "https://air.tianruixinchengyun.com/api/statistics/air/time"

    all_statistics = []
    error_devices = []  # 记录请求失败的设备

    print(f"\n开始获取第二个接口数据，共{len(device_list)}台设备...")

    for device in tqdm(device_list, desc="处理设备"):
        device_id = device["设备id"]
        device_serial = device["设备编号"]
        location = device["位置"]

        payload = {
            "page": 1,
            "pageSize": page_size,
            "sorts": [],
            "airId": device_id,
            "startTime": START_TIME,
            "endTime": END_TIME
        }

        try:
            # 首次请求获取总页数
            response = requests.post(url, json=payload, headers=headers)

            # 检查响应状态码
            if response.status_code == 404:
                print(f"\n设备 {device_serial} 请求返回404，可能是接口URL错误，尝试备用URL...")
                # 尝试备用URL
                backup_url = "https://air.tianruixinchengyun.com/api/airConditioner/record/page"
                backup_response = requests.post(backup_url, json=payload, headers=headers)
                backup_response.raise_for_status()
                first_data = backup_response.json()
                print(f"设备 {device_serial} 备用URL请求成功")
            else:
                response.raise_for_status()
                first_data = response.json()

            if first_data.get("code") == 0:
                data = first_data.get("data", {})
                total_pages = data.get("pageCount", 1)

                # 处理当前设备的所有页面
                for page in range(1, total_pages + 1):
                    if page > 1:
                        payload["page"] = page
                        page_response = requests.post(url, json=payload, headers=headers)
                        page_response.raise_for_status()
                        page_data = page_response.json()
                        page_items = page_data.get("data", {}).get("items", [])
                    else:
                        # 第一页使用首次请求数据
                        page_items = data.get("items", [])

                    # 处理当前页的所有记录
                    for record in page_items:
                        # 拆分记录时间
                        record_time = record.get("recordTime", "")
                        if record_time:
                            # 拆分日期和时间
                            parts = record_time.split(" ", 1)
                            date_part = parts[0] if len(parts) > 0 else ""
                            time_part = parts[1] if len(parts) > 1 else ""
                        else:
                            date_part, time_part = "", ""

                        # 添加设备信息并拆分时间
                        stat_record = {
                            "设备id": device_id,
                            "设备编号": device_serial,
                            "位置": location,
                            "记录日期": date_part,
                            "记录时间": time_part,
                            "温度": record.get("temperature"),
                            "湿度": record.get("humidity"),
                            "模式": record.get("mode"),
                            "风速": record.get("windSpeed"),
                            "开关状态": record.get("switchStatus"),
                            "设定温度": record.get("settingTemperature")
                        }
                        all_statistics.append(stat_record)

                    # 接口请求间隔
                    time.sleep(request_delay)
        except requests.exceptions.RequestException as e:
            print(f"\n设备 {device_serial} 请求失败: {e}")
            error_devices.append(device_serial)
            continue

    # 保存第二个接口的数据到Excel
    if all_statistics:
        df = pd.DataFrame(all_statistics)
        df.to_excel(statistics_file, index=False)
        print(f"\n第二个接口数据提取完成，共{len(all_statistics)}条记录，已保存至 {statistics_file}")

        # 如果有失败的设备，打印出来
        if error_devices:
            print(f"\n以下设备请求失败: {', '.join(error_devices)}")

        return True
    else:
        print("\n未获取到任何统计数据")
        return False


# --------------------------
# 主程序流程
# --------------------------
if __name__ == "__main__":
    # 第一步：获取设备信息
    devices = get_device_info()

    if devices:
        # 第二步：获取并处理统计数据
        success = get_device_statistics(devices)
        if success:
            print("\n程序执行完成！")
        else:
            print("\n程序执行完成，但未获取到统计数据")
    else:
        print("\n无法获取设备信息，程序终止")