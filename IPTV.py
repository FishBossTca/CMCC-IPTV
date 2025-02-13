import requests
import os
import json
import re


# 解码 Unicode 编码的函数
def decode_unicode(data):
    """递归地解码数据中的\\u 开头的 Unicode 编码"""
    if isinstance(data, dict):
        for key, value in data.items():
            data[key] = decode_unicode(value)
    elif isinstance(data, list):
        for i in range(len(data)):
            data[i] = decode_unicode(data[i])
    elif isinstance(data, str):
        # 只解码 \u 开头的 Unicode 编码
        return re.sub(
            r"\\u[0-9a-fA-F]{4}",
            lambda match: bytes(match.group(0), "utf-8").decode("unicode_escape"),
            data,
        )
    return data


# 获取总频道信息并保存
class ChannelInfoFetcher:
    def __init__(self, url, save_dir, file_name):
        self.url = url
        self.save_dir = save_dir
        self.file_name = file_name

    def fetch_and_save(self):
        response = requests.get(self.url)
        response.raise_for_status()

        data = response.json()
        file_path = os.path.join(self.save_dir, self.file_name)

        # 确保目录存在
        os.makedirs(self.save_dir, exist_ok=True)

        # 保存总频道信息
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        print(f"总频道信息已保存为 {file_path}")
        return data


# 获取各个频道组信息并保存
class DataLinkFetcher:
    def __init__(self, data, save_dir):
        self.data = data
        self.save_dir = save_dir

    def fetch_and_save_data_links(self):
        data_links = []

        # 提取所有 dataLink 和 itemTitle
        for area in self.data["areaDatas"]:
            for item in area["items"]:
                item_title = item["itemTitle"]
                data_link = item["dataLink"]
                filename = f"{item_title}.json".replace(" ", "_").replace("/", "_")
                data_links.append((data_link, filename))

        # 下载并保存每个 dataLink 文件
        for link, filename in data_links:
            print(f"正在下载 {link}")
            file_response = requests.get(link)
            file_response.raise_for_status()

            # 获取文件内容
            file_content = file_response.json()

            # 解码文件内容中的 Unicode 编码
            decoded_content = decode_unicode(file_content)

            # 保存解码后的文件到指定目录
            file_path = os.path.join(self.save_dir, filename)
            os.makedirs(self.save_dir, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(decoded_content, f, ensure_ascii=False, indent=4)

            print(f"文件已保存为 {file_path}")

        print("所有 dataLink 文件下载完成!")


# 获取各个频道信息并保存
class NestedDataLinkFetcher:
    def __init__(self, data_links_dir, save_dir):
        self.data_links_dir = data_links_dir
        self.save_dir = save_dir

    def fetch_and_process_nested_data_links(self):
        # 获取保存的文件
        files = [f for f in os.listdir(self.data_links_dir) if f.endswith(".json")]

        # 处理每个文件中的 dataLink
        for file_name in files:
            file_path = os.path.join(self.data_links_dir, file_name)
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)

            # 提取每个 dataLink 和 itemTitle
            for item in content.get(
                "categoryitem", []
            ):  # 使用 'categoryitem' 来提取每个频道
                item_title = item.get("itemTitle", "Unknown Title")
                data_link = item.get("dataLink")

                if data_link:
                    filename = f"{item_title}.json".replace(" ", "_").replace("/", "_")

                    # 下载 dataLink 文件
                    try:
                        print(f"正在下载 {data_link}")
                        file_response = requests.get(data_link)
                        file_response.raise_for_status()

                        # 获取文件内容
                        file_content = file_response.json()

                        # 解码文件内容中的 Unicode 编码
                        decoded_content = decode_unicode(file_content)

                        # 保存解码后的文件到指定目录
                        file_path = os.path.join(self.save_dir, filename)
                        os.makedirs(self.save_dir, exist_ok=True)

                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(decoded_content, f, ensure_ascii=False, indent=4)

                        print(f"文件已保存为 {file_path}")
                    except requests.exceptions.RequestException as e:
                        print(f"下载失败: {data_link} 错误信息: {e}")

        print("所有嵌套 dataLink 文件下载完成!")


# 获取各个频道图片并保存
class ImageDownloader:
    def __init__(self, image_dir):
        self.image_dir = image_dir
        os.makedirs(self.image_dir, exist_ok=True)

    def download(self, url):
        """下载图片并返回保存的本地路径"""
        if not url:
            return ""

        img_name = url.split("/")[-1]
        img_path = os.path.join(self.image_dir, img_name)

        if os.path.exists(img_path):
            return img_path

        try:
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(img_path, "wb") as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                print(f"下载图片: {img_path}")
            else:
                print(f"图片下载失败: {url}")
        except Exception as e:
            print(f"下载图片时出错: {e}")

        return img_path

# 将各频道转换为m3u格式文件
class ChannelToM3U:
    def __init__(self, input_file, output_file, image_downloader, category_dir):
        self.input_file = input_file
        self.output_file = output_file
        self.image_downloader = image_downloader
        self.category_dir = category_dir
        self.channel_categories = self.load_channel_categories()
        self.seen_urls = set()  # 用于存储已处理的URL

    def load_channel_categories(self):
        """读取/getChannelCategory2/目录中的所有JSON文件，除去排除的文件"""
        category_files = [
            f
            for f in os.listdir(self.category_dir)
            if f.endswith(".json") and f not in ["本地.json", "超清.json", "高清.json"]
        ]
        category_data = {}

        for category_file in category_files:
            category_path = os.path.join(self.category_dir, category_file)
            with open(category_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("categoryitem", []):
                    item_code = item["itemCode"]
                    if item_code not in category_data:
                        category_data[item_code] = []
                    category_data[item_code].append(
                        category_file.replace(".json", "")
                    )  # 使用文件名作为分组名
        return category_data

    def convert_to_m3u(self):
        m3u_content = "#EXTM3U\n"

        with open(self.input_file, "r", encoding="utf-8") as f:
            channel_data = json.load(f)

        output_dir = os.path.dirname(self.output_file)

        for channel in channel_data.get("channels", []):
            title = channel["title"]
            icon = channel["icon"]
            channelnum = channel["channelnum"]
            code = channel["code"]

            icon_path = self.image_downloader.download(icon)

            max_bitrate_url = None

            for phychannel in channel["phychannels"]:
                if "params" in phychannel:
                    rtp_url = phychannel["params"].get("hwurl", "")
                    if rtp_url:
                        max_bitrate_url = rtp_url
                        break  # 获取第一个有效的URL，忽略其他分辨率

            if max_bitrate_url:
                # 检查重复URL
                if max_bitrate_url in self.seen_urls:
                    print(f"重复的URL: {max_bitrate_url}，频道: {title}")
                else:
                    self.seen_urls.add(max_bitrate_url)

                # 获取额外的分组（如广东等）
                extra_groups = self.channel_categories.get(code, [])

                # 处理分组：
                # 1. 如果有 "全部"，去除 "全部" 分组
                # 2. 如果没有其他分组，添加 "其他" 分组
                if "全部" in extra_groups:
                    extra_groups.remove("全部")

                if len(extra_groups) == 0:
                    extra_groups = ["其他"]

                m3u_content += self.create_m3u_entry(
                    channel, extra_groups, icon_path, max_bitrate_url
                )

        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(m3u_content)

        print(f"M3U 文件已保存为 {self.output_file}")

    def create_m3u_entry(self, channel, group_titles, icon_path, url):
        """创建带有group-title的M3U条目"""
        display_name = f"{channel['title']}"

        # 确保每个分组名都被双引号包裹并且多个分组之间用逗号分隔
        group_title_str = ",".join([f'"{group}"' for group in group_titles])

        return (
            f"#EXTINF:-1 tvg-id=\"{channel['code']}\" "
            f"tvg-name=\"{channel['title']}\" "
            f'tvg-logo="{icon_path}" '
            f"tvg-channelnum=\"{channel['channelnum']}\" "
            f"group-title={group_title_str},"
            f"{display_name}\n"
            f"{url}\n"
        )


# 主执行流程
if __name__ == "__main__":
    # 步骤1: 获取总频道信息并保存
    channel_url = "http://183.235.16.92:8082/epg/api/custom/getChannelCategory.json"
    channel_url2 = "http://183.235.16.92:8082/epg/api/custom/getChannelCategory2.json"
    channel_url3 = "http://183.235.16.92:8082/epg/api/custom/getChannelCategory3.json"
    all_channel_url = "http://183.235.16.92:8082/epg/api/custom/getAllChannel.json"
    all_channel_url2 = "http://183.235.16.92:8082/epg/api/custom/getAllChannel2.json"

    # 频道总信息保存位置
    all_channel_save_dir = channel_save_dir = "./频道总信息"

    channel_info_fetcher = ChannelInfoFetcher(
        channel_url, channel_save_dir, "getChannelCategory.json"
    )
    channel_info_fetcher2 = ChannelInfoFetcher(
        channel_url2, channel_save_dir, "getChannelCategory2.json"
    )
    channel_info_fetcher3 = ChannelInfoFetcher(
        channel_url3, channel_save_dir, "getChannelCategory3.json"
    )
    all_channel_fetcher = ChannelInfoFetcher(
        all_channel_url, all_channel_save_dir, "getAllChannel.json"
    )
    all_channel_fetcher2 = ChannelInfoFetcher(
        all_channel_url2, all_channel_save_dir, "getAllChannel2.json"
    )

    data = channel_info_fetcher.fetch_and_save()
    data2 = channel_info_fetcher2.fetch_and_save()
    data3 = channel_info_fetcher3.fetch_and_save()
    all_channel_fetcher.fetch_and_save()
    all_channel_fetcher2.fetch_and_save()

    # 步骤2: 获取并下载 dataLink 文件并保存
    # 各个节目组频道保存路径
    data_links_save_dir = "./获取各个节目组频道"
    getChannelCategory = data_links_save_dir + "/getChannelCategory"
    getChannelCategory2 = data_links_save_dir + "/getChannelCategory2"
    getChannelCategory3 = data_links_save_dir + "/getChannelCategory3"
    data_link_fetcher = DataLinkFetcher(data, getChannelCategory)
    data_link_fetcher2 = DataLinkFetcher(data2, getChannelCategory2)
    data_link_fetcher3 = DataLinkFetcher(data3, getChannelCategory3)
    data_link_fetcher.fetch_and_save_data_links()
    data_link_fetcher2.fetch_and_save_data_links()
    data_link_fetcher3.fetch_and_save_data_links()

    # 步骤3: 获取并处理嵌套的 dataLink
    # 各个节目组频道保存路径
    each_channel_info_save_dir = "./获取各个频道信息"
    nested_data_link_fetcher = NestedDataLinkFetcher(
        getChannelCategory, each_channel_info_save_dir + "/getChannelCategory"
    )
    nested_data_link_fetcher2 = NestedDataLinkFetcher(
        getChannelCategory2, each_channel_info_save_dir + "/getChannelCategory2"
    )
    nested_data_link_fetcher.fetch_and_process_nested_data_links()
    nested_data_link_fetcher2.fetch_and_process_nested_data_links()

    # 步骤4：获取台标和
    input_file = "./频道总信息/getAllChannel2.json"  # 指定的 JSON 文件路径
    output_file = "./M3U文件输出/iptv.m3u"  # 输出的 M3U 文件路径
    category_dir = "./获取各个节目组频道/getChannelCategory2"
    image_dir = "./images"  # 图片保存目录

    # 创建 ImageDownloader 实例
    image_downloader = ImageDownloader(image_dir)
    # 步骤5：将数据转换成m3u格式

    # 创建 ChannelToM3U 实例
    channel_to_m3u = ChannelToM3U(
        input_file, output_file, image_downloader, category_dir
    )
    channel_to_m3u.convert_to_m3u()

    print("所有任务完成！")
