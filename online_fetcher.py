# online_fetcher.py
"""
在线资源获取模块
- 来源：网易云音乐增强API (本地部署推荐)
"""
import sys
import requests
import re
from PIL import Image
from io import BytesIO
import os

# 禁用 SSL 警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class OnlineFetcher:
    """在线资源获取器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.timeout = 10  # 请求超时时间（秒）
        
        # ===== 网易云音乐增强API配置 =====
        # 项目地址: https://github.com/NeteaseCloudMusicApiEnhanced/api-enhanced
        # 推荐本地部署：http://localhost:3000
        self.netease_api = "http://yourip:3000"  # ← 修改为你的API地址
        
        # 创建缓存目录（兼容脚本和EXE）
        if getattr(sys, 'frozen', False):
            script_dir = os.path.dirname(sys.executable)
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.cache_dir = os.path.join(script_dir, "sinf")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            print(f"[缓存] 创建缓存目录: {self.cache_dir}")
    
    # ==================== 公开接口 ====================
    
    def fetch_lyrics(self, title, artist):
        """
        获取歌词（优先级：缓存 → 网易云）
        :return: (lyrics_map, time_points)
        """
        print(f"[在线获取] 正在搜索歌词: {title} - {artist}")
        
        # 1. 检查本地缓存
        lyrics_map, time_points = self._load_lyrics_from_cache(title)
        if lyrics_map:
            return lyrics_map, time_points
        
        # 2. 从网易云API获取
        lyrics_map, time_points, lrc_text = self._fetch_lyrics_from_netease(title, artist)
        if lyrics_map:
            print(f"[在线获取] ✓ 成功获取歌词（来源：网易云）")
            self._save_lyrics_to_file(title, lrc_text)
            return lyrics_map, time_points
        
        print(f"[在线获取] ✗ 未找到歌词")
        return {}, []
    
    def fetch_cover(self, title, artist):
        """
        获取封面（优先级：缓存 → 网易云）
        :return: PIL Image 对象或 None
        """
        print(f"[在线获取] 正在搜索封面: {title} - {artist}")
        
        # 1. 检查本地缓存
        cover = self._load_cover_from_cache(title)
        if cover:
            return cover
        
        # 2. 从网易云获取
        cover = self._fetch_cover_from_netease(title, artist)
        if cover:
            print(f"[在线获取] ✓ 成功获取封面（来源：网易云）")
            self._save_cover_to_file(title, cover)
            return cover
        
        print(f"[在线获取] ✗ 未找到封面")
        return None
    
    # ==================== 网易云API ====================
    
    def _fetch_lyrics_from_netease(self, title, artist):
        """从网易云音乐增强API获取歌词"""
        try:
            # 步骤1: 搜索歌曲
            print(f"[网易云-歌词] 搜索歌曲...")
            search_url = f"{self.netease_api}/search"
            params = {
                'keywords': f"{title} {artist}",
                'type': 1,  # 单曲
                'limit': 5   # 获取前5个结果
            }
            
            response = self.session.get(search_url, params=params, timeout=self.timeout)
            if response.status_code != 200:
                print(f"[网易云-歌词] 搜索失败 (状态码: {response.status_code})")
                return {}, [], None
            
            data = response.json()
            songs = data.get('result', {}).get('songs', [])
            
            if not songs:
                print(f"[网易云-歌词] 未找到歌曲")
                return {}, [], None
            
            # 步骤2: 尝试多个搜索结果（提高准确性）
            for i, song in enumerate(songs[:3], 1):
                song_id = song['id']
                song_name = song['name']
                artists = '/'.join([ar['name'] for ar in song.get('artists', [])])
                
                print(f"[网易云-歌词] 尝试 {i}/3: {song_name} - {artists} (ID: {song_id})")
                
                # 步骤3: 获取歌词
                lyric_url = f"{self.netease_api}/lyric"
                lyric_response = self.session.get(
                    lyric_url,
                    params={'id': song_id},
                    timeout=self.timeout
                )
                
                if lyric_response.status_code != 200:
                    print(f"[网易云-歌词] 获取失败 (状态码: {lyric_response.status_code})")
                    continue
                
                lyric_data = lyric_response.json()
                lrc_text = lyric_data.get('lrc', {}).get('lyric', '')
                
                if lrc_text:
                    # 步骤4: 解析歌词
                    lyrics_map, time_points = self._parse_lrc(lrc_text)
                    if lyrics_map:
                        print(f"[网易云-歌词] ✓ 获取成功 ({len(lyrics_map)}行)")
                        return lyrics_map, time_points, lrc_text
                    else:
                        print(f"[网易云-歌词] 歌词格式无效")
                else:
                    print(f"[网易云-歌词] 该歌曲无歌词")
            
            print(f"[网易云-歌词] 所有结果均无有效歌词")
            return {}, [], None
            
        except requests.exceptions.Timeout:
            print(f"[网易云-歌词] 连接超时")
            return {}, [], None
        except requests.exceptions.ConnectionError:
            print(f"[网易云-歌词] 连接失败 - 请确认API运行: {self.netease_api}")
            return {}, [], None
        except Exception as e:
            print(f"[网易云-歌词] 异常: {e}")
            return {}, [], None
    
    def _fetch_cover_from_netease(self, title, artist):
        """从网易云音乐增强API获取封面"""
        try:
            # 步骤1: 搜索歌曲，获取ID
            print(f"[网易云-封面] 搜索歌曲...")
            search_url = f"{self.netease_api}/search"
            params = {
                'keywords': f"{title} {artist}",
                'type': 1,  # 单曲
                'limit': 1
            }
            
            response = self.session.get(search_url, params=params, timeout=self.timeout)
            if response.status_code != 200:
                print(f"[网易云-封面] 搜索失败 (状态码: {response.status_code})")
                return None
            
            data = response.json()
            songs = data.get('result', {}).get('songs', [])
            
            if not songs:
                print(f"[网易云-封面] 未找到歌曲")
                return None
            
            # 获取第一个结果的歌曲ID
            song_id = songs[0]['id']
            song_name = songs[0]['name']
            artists = '/'.join([ar['name'] for ar in songs[0].get('artists', [])])
            
            print(f"[网易云-封面] 找到: {song_name} - {artists} (ID: {song_id})")
            
            # 步骤2: 使用 /song/detail 获取详细信息
            print(f"[网易云-封面] 获取歌曲详情...")
            detail_url = f"{self.netease_api}/song/detail"
            detail_response = self.session.get(
                detail_url,
                params={'ids': song_id},
                timeout=self.timeout
            )
            
            if detail_response.status_code != 200:
                print(f"[网易云-封面] 获取详情失败 (状态码: {detail_response.status_code})")
                return None
            
            detail_data = detail_response.json()
            songs_detail = detail_data.get('songs', [])
            
            if not songs_detail:
                print(f"[网易云-封面] 详情数据为空")
                return None
            
            # 步骤3: 提取专辑封面URL
            album = songs_detail[0].get('al', {})  # 'al' 是 album 的缩写
            cover_url = album.get('picUrl')
            
            if not cover_url:
                print(f"[网易云-封面] 未找到封面URL")
                return None
            
            print(f"[网易云-封面] 封面URL: {cover_url[:60]}...")
            
            # 步骤4: 下载封面图片
            print(f"[网易云-封面] 下载封面...")
            img_response = self.session.get(cover_url, timeout=self.timeout)
            if img_response.status_code != 200:
                print(f"[网易云-封面] 下载失败 (状态码: {img_response.status_code})")
                return None
            
            # 步骤5: 转换为PIL Image对象
            cover_image = Image.open(BytesIO(img_response.content))
            print(f"[网易云-封面] ✓ 封面下载成功 ({cover_image.size[0]}x{cover_image.size[1]})")
            
            return cover_image
            
        except requests.exceptions.Timeout:
            print(f"[网易云-封面] 连接超时")
            return None
        except requests.exceptions.ConnectionError:
            print(f"[网易云-封面] 连接失败 - 请确认API运行: {self.netease_api}")
            return None
        except Exception as e:
            print(f"[网易云-封面] 异常: {e}")
            return None
    
    # ==================== 工具方法 ====================
    
    def _parse_lrc(self, lrc_text):
        """解析LRC格式歌词"""
        lyrics_map = {}
        time_points = []
        
        # LRC格式: [mm:ss.xx]歌词文本
        pattern = r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)'
        
        for line in lrc_text.split('\n'):
            match = re.match(pattern, line)
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                milliseconds = int(match.group(3))
                text = match.group(4).strip()
                
                time_in_seconds = minutes * 60 + seconds + milliseconds / 1000
                
                if text:
                    lyrics_map[time_in_seconds] = text
                    time_points.append(time_in_seconds)
        
        time_points.sort()
        return lyrics_map, time_points
    
    def _get_safe_filename(self, title):
        """生成安全的文件名"""
        invalid_chars = '<>:"/\\|?*'
        safe_name = title
        for char in invalid_chars:
            safe_name = safe_name.replace(char, '_')
        if len(safe_name) > 200:
            safe_name = safe_name[:200]
        return safe_name
    
    # ==================== 本地缓存 ====================
    
    def _save_lyrics_to_file(self, title, lrc_text):
        """保存歌词到本地"""
        try:
            safe_title = self._get_safe_filename(title)
            lrc_path = os.path.join(self.cache_dir, f"{safe_title}.lrc")
            
            with open(lrc_path, 'w', encoding='utf-8') as f:
                f.write(lrc_text)
            
            print(f"[缓存] 歌词已保存: {safe_title}.lrc")
        except Exception as e:
            print(f"[缓存] 保存歌词失败: {e}")
    
    def _save_cover_to_file(self, title, cover_image):
        """保存封面到本地"""
        try:
            safe_title = self._get_safe_filename(title)
            
            # 转换为RGB模式
            if cover_image.mode in ('RGBA', 'LA', 'P'):
                rgb_image = Image.new('RGB', cover_image.size, (255, 255, 255))
                if cover_image.mode == 'P':
                    cover_image = cover_image.convert('RGBA')
                rgb_image.paste(cover_image, mask=cover_image.split()[-1] if cover_image.mode == 'RGBA' else None)
                cover_image = rgb_image
            
            jpg_path = os.path.join(self.cache_dir, f"{safe_title}.jpg")
            cover_image.save(jpg_path, 'JPEG', quality=95)
            
            print(f"[缓存] 封面已保存: {safe_title}.jpg")
        except Exception as e:
            print(f"[缓存] 保存封面失败: {e}")
    
    def _load_lyrics_from_cache(self, title):
        """从缓存加载歌词"""
        try:
            safe_title = self._get_safe_filename(title)
            lrc_path = os.path.join(self.cache_dir, f"{safe_title}.lrc")
            
            if os.path.exists(lrc_path):
                with open(lrc_path, 'r', encoding='utf-8') as f:
                    lrc_text = f.read()
                
                lyrics_map, time_points = self._parse_lrc(lrc_text)
                if lyrics_map:
                    print(f"[缓存] ✓ 从缓存加载歌词: {safe_title}.lrc")
                    return lyrics_map, time_points
            
            return {}, []
        except Exception:
            return {}, []
    
    def _load_cover_from_cache(self, title):
        """从缓存加载封面"""
        try:
            safe_title = self._get_safe_filename(title)
            jpg_path = os.path.join(self.cache_dir, f"{safe_title}.jpg")
            
            if os.path.exists(jpg_path):
                cover_image = Image.open(jpg_path)
                print(f"[缓存] ✓ 从缓存加载封面: {safe_title}.jpg")
                return cover_image
            
            return None
        except Exception:
            return None


# ==================== 全局实例 ====================

_fetcher = None

def get_fetcher():
    """获取全局在线获取器实例"""
    global _fetcher
    if _fetcher is None:
        _fetcher = OnlineFetcher()
    return _fetcher

def fetch_lyrics_online(title, artist):
    """便捷函数：从网络获取歌词"""
    fetcher = get_fetcher()
    return fetcher.fetch_lyrics(title, artist)

def fetch_cover_online(title, artist):
    """便捷函数：从网络获取封面"""
    fetcher = get_fetcher()
    return fetcher.fetch_cover(title, artist)