from pkg.plugin.context import register, handler, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
import json
import os
import re
from pkg.platform.types import message as platform_message
from pkg.provider import entities as llm_entities

@register(name="Ai表情包", description="让大模型学会发表情包", version="0.1", author="小馄饨")
class EmoticonPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        super().__init__(host)
        self.emoticons = {}
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.images_dir = os.path.join(self.plugin_dir, "images")
        self.load_emoticons()

    async def initialize(self):
        pass

    def load_emoticons(self):
        if not os.path.exists(self.images_dir):
            os.makedirs(self.images_dir)
        for file in os.listdir(self.images_dir):
            name, ext = os.path.splitext(file)
            if ext.lower() in ['.gif', '.png', '.jpg', '.jpeg', '.webp']:
                self.emoticons[name] = os.path.join(self.images_dir, file)
        config_path = os.path.join(self.plugin_dir, "config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump({"emoticons": list(self.emoticons.keys())}, f, ensure_ascii=False, indent=4)

    @handler(PromptPreProcessing)
    async def handle_prompt_preprocessing(self, ctx: EventContext):
        emoticon_list = ", ".join(self.emoticons.keys())
        emoticon_prompt = llm_entities.Message(
            role='system',
            content=f"你可以在对话中使用表情包来表达情感、心情、态度，用户收到的表情包图片会显示在消息前面，格式为[:表情名]。当前支持的表情: {emoticon_list}。"
        )
        last_user_index = -1
        for i, prompt in enumerate(ctx.event.default_prompt):
            if prompt.role == 'user':
                last_user_index = i
        if last_user_index != -1:
            ctx.event.default_prompt.insert(last_user_index + 1, emoticon_prompt)
        else:
            ctx.event.default_prompt.append(emoticon_prompt)

    def process_emoticons(self, text):
        image_paths = []
        modified_text = text
        pattern = r'\[:([\w\u4e00-\u9fff]+)\]'
        matches = re.finditer(pattern, text)
        for match in matches:
            emoticon_name = match.group(1)
            if emoticon_name in self.emoticons:
                image_paths.append(self.emoticons[emoticon_name])
                modified_text = modified_text.replace(match.group(0), '')
            else:
                self.host.ap.logger.warning(f"未找到表情: {emoticon_name}")
        
        return modified_text.strip(), image_paths

    @handler(PersonNormalMessageReceived)
    async def handle_private_message(self, ctx: EventContext):
        msg = ctx.event.text_message
        modified_text, image_paths = self.process_emoticons(msg)
        
        if image_paths:
            if modified_text:
                ctx.add_return("reply", [platform_message.Plain(modified_text)])
            
            for image_path in image_paths:
                ctx.add_return("reply", [platform_message.Image(path=image_path)])
            
            ctx.prevent_default()

    @handler(GroupNormalMessageReceived)
    async def handle_group_message(self, ctx: EventContext):
        msg = ctx.event.text_message
        modified_text, image_paths = self.process_emoticons(msg)
        
        if image_paths:
            if modified_text:
                ctx.add_return("reply", [platform_message.Plain(modified_text)])
            
            for image_path in image_paths:
                ctx.add_return("reply", [platform_message.Image(path=image_path)])
            
            ctx.prevent_default()

    @handler(NormalMessageResponded)
    async def handle_model_response(self, ctx: EventContext):
        modified_text, image_paths = self.process_emoticons(ctx.event.response_text)
        
        if image_paths:
            ctx.prevent_default()
            
            for image_path in image_paths:
                await ctx.send_message(
                    ctx.event.launcher_type,
                    ctx.event.launcher_id,
                    [platform_message.Image(path=image_path)]
                )
            
            if modified_text:
                await ctx.send_message(
                    ctx.event.launcher_type,
                    ctx.event.launcher_id,
                    [platform_message.Plain(modified_text)]
                ) 