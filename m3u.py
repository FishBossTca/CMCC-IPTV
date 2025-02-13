import os
import json
import requests

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
                with open(img_path, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                print(f"下载图片: {img_path}")
            else:
                print(f"图片下载失败: {url}")
        except Exception as e:
            print(f"下载图片时出错: {e}")
        
        return img_path

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
        category_files = [f for f in os.listdir(self.category_dir) if f.endswith('.json') and f not in ['本地.json', '超清.json', '高清.json']]
        category_data = {}

        for category_file in category_files:
            category_path = os.path.join(self.category_dir, category_file)
            with open(category_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data.get('categoryitem', []):
                    item_code = item['itemCode']
                    if item_code not in category_data:
                        category_data[item_code] = []
                    category_data[item_code].append(category_file.replace('.json', ''))  # 使用文件名作为分组名
        return category_data

    def convert_to_m3u(self):
        m3u_content = "#EXTM3U\n"
        
        with open(self.input_file, 'r', encoding='utf-8') as f:
            channel_data = json.load(f)

        output_dir = os.path.dirname(self.output_file)

        for channel in channel_data.get('channels', []):
            title = channel['title']
            icon = channel['icon']
            channelnum = channel['channelnum']
            code = channel['code']

            icon_path = self.image_downloader.download(icon)

            max_bitrate_url = None

            for phychannel in channel['phychannels']:
                if 'params' in phychannel:
                    rtp_url = phychannel['params'].get('hwurl', '')
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

                m3u_content += self.create_m3u_entry(channel, extra_groups, icon_path, max_bitrate_url)

        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(m3u_content)

        print(f"M3U 文件已保存为 {self.output_file}")

    def create_m3u_entry(self, channel, group_titles, icon_path, url):
        """创建带有group-title的M3U条目"""
        display_name = f"{channel['title']}"
        
        # 确保每个分组名都被双引号包裹并且多个分组之间用逗号分隔
        group_title_str = ','.join([f'"{group}"' for group in group_titles])

        return (
            f"#EXTINF:-1 tvg-id=\"{channel['code']}\" "
            f"tvg-name=\"{channel['title']}\" "
            f"tvg-logo=\"{icon_path}\" "
            f"tvg-channelnum=\"{channel['channelnum']}\" "
            f'group-title={group_title_str},'
            f"{display_name}\n"
            f"{url}\n"
        )

if __name__ == '__main__':
    input_file = './频道总信息/getAllChannel2.json'
    output_file = './频道.m3u'
    image_dir = './images'
    category_dir = './获取各个节目组频道/getChannelCategory2'
    
    image_downloader = ImageDownloader(image_dir)
    channel_to_m3u = ChannelToM3U(input_file, output_file, image_downloader, category_dir)
    channel_to_m3u.convert_to_m3u()
