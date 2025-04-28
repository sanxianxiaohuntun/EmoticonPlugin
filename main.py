from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
import json
import os
import re
from pkg.platform.types import message as platform_message
from pkg.provider import entities as llm_entities

@register(name="Ai表情包", description="让大模型学会发表情包", version="0.2", author="小馄饨")
class EmoticonPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        super().__init__(host)
        self.emoticons = {}
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.images_dir = os.path.join(self.plugin_dir, "images")
        self.config_path = os.path.join(self.plugin_dir, "config.json")
        
        # 加载配置
        self.load_config()
        # 加载表情包
        self.load_emoticons()

    async def initialize(self):
        pass

    def load_config(self):
        """
        加载配置文件，如果不存在则创建默认配置
        配置项包括：
        - url_prefix: 表情包图片URL前缀，用于构建表情包图片URL
        - use_url: 是否使用URL方式发送表情包，适用于Gewechat等只支持URL的适配器
        """
        default_config = {
            "url_prefix": "",  # 默认为空，用户需要自行设置
            "use_url": False,  # 默认不使用URL方式
            "emoticons": []    # 表情包列表，会在load_emoticons中更新
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 确保配置项完整
                    if "url_prefix" not in config:
                        config["url_prefix"] = default_config["url_prefix"]
                    if "use_url" not in config:
                        config["use_url"] = default_config["use_url"]
                    self.config = config
            except Exception as e:
                self.host.ap.logger.error(f"加载表情包配置失败: {e}")
                self.config = default_config
        else:
            self.config = default_config
            self.save_config()
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.host.ap.logger.error(f"保存表情包配置失败: {e}")

    def load_emoticons(self):
        """加载表情包图片"""
        if not os.path.exists(self.images_dir):
            os.makedirs(self.images_dir)
        
        # 清空现有表情包
        self.emoticons = {}
        
        # 加载表情包图片
        for file in os.listdir(self.images_dir):
            name, ext = os.path.splitext(file)
            if ext.lower() in ['.gif', '.png', '.jpg', '.jpeg', '.webp']:
                self.emoticons[name] = file
        
        # 更新配置中的表情包列表
        self.config["emoticons"] = list(self.emoticons.keys())
        self.save_config()

    @handler(PromptPreProcessing)
    async def handle_prompt_preprocessing(self, ctx: EventContext):
        """向AI提示中添加表情包使用说明"""
        emoticon_list = ", ".join(self.emoticons.keys())
        emoticon_prompt = llm_entities.Message(
            role='system',
            content=f"你可以在对话中使用表情包来表达情感、心情、态度，格式为%表情名%。当你使用表情包时，用户会看到相应的表情图片。每条对话只允许使用一个表情包。当前支持的表情: {emoticon_list}。"
        )
        
        # 在最后一条用户消息后插入表情包提示
        last_user_index = -1
        for i, prompt in enumerate(ctx.event.default_prompt):
            if prompt.role == 'user':
                last_user_index = i
        
        if last_user_index != -1:
            ctx.event.default_prompt.insert(last_user_index + 1, emoticon_prompt)
        else:
            ctx.event.default_prompt.append(emoticon_prompt)

    def process_emoticons(self, text):
        """
        处理文本中的表情标记，提取表情包
        返回：修改后的文本和表情包路径列表
        """
        image_paths = []
        image_urls = []
        modified_text = text
        pattern = r'%([\w\u4e00-\u9fff]+)%'
        matches = re.finditer(pattern, text)
        
        for match in matches:
            emoticon_name = match.group(1)
            if emoticon_name in self.emoticons:
                # 获取表情包文件名
                file_name = self.emoticons[emoticon_name]
                # 构建本地路径
                image_path = os.path.join(self.images_dir, file_name)
                image_paths.append(image_path)
                
                # 如果配置了URL前缀，构建URL
                if self.config.get("url_prefix"):
                    image_url = f"{self.config['url_prefix']}/{file_name}"
                    image_urls.append(image_url)
                
                # 从文本中移除表情标记
                modified_text = modified_text.replace(match.group(0), '')
            else:
                self.host.ap.logger.warning(f"未找到表情: {emoticon_name}")
        
        return modified_text.strip(), image_paths, image_urls

    @handler(NormalMessageResponded)
    async def handle_model_response(self, ctx: EventContext):
        """处理模型响应，发送表情包"""
        modified_text, image_paths, image_urls = self.process_emoticons(ctx.event.response_text)
        
        # 检查是否有表情包
        if not image_paths:
            return
        
        # 阻止默认处理
        ctx.prevent_default()
        
        # 获取平台适配器类型
        platform_type = ctx.event.launcher_type
        
        # 检查是否使用URL方式发送表情包
        use_url = self.config.get("use_url", False)
        
        # 如果是Gewechat适配器或配置为使用URL，且有URL前缀配置
        if (platform_type == "gewechat" or use_url) and self.config.get("url_prefix") and image_urls:
            try:
                # 使用URL发送表情包
                for image_url in image_urls:
                    self.host.ap.logger.info(f"发送表情包 URL: {image_url}")
                    
                    # 发送图片消息，使用url参数
                    await ctx.send_message(
                        ctx.event.launcher_type,
                        ctx.event.launcher_id,
                        [platform_message.Image(url=image_url)]
                    )
                    
                    self.host.ap.logger.info(f"已发送表情图片 URL: {image_url}")
                    # 只发送第一个表情包
                    break
            except Exception as e:
                self.host.ap.logger.error(f"发送表情图片失败: {e}")
        else:
            # 使用本地路径发送表情包
            try:
                for image_path in image_paths:
                    self.host.ap.logger.info(f"发送表情包: {image_path}")
                    
                    # 发送图片消息，使用path参数
                    await ctx.send_message(
                        ctx.event.launcher_type,
                        ctx.event.launcher_id,
                        [platform_message.Image(path=image_path)]
                    )
                    
                    # 只发送第一个表情包
                    break
            except Exception as e:
                self.host.ap.logger.error(f"发送表情图片失败: {e}")
        
        # 如果还有文本内容，发送文本消息
        if modified_text:
            await ctx.send_message(
                ctx.event.launcher_type,
                ctx.event.launcher_id,
                [platform_message.Plain(modified_text)]
            )
