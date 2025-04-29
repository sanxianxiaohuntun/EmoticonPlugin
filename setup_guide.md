# 表情包 URL 功能设置指南

这是我（Jarvis0225）编写的设置指南，帮助你设置表情包 URL 功能，使 LangBot 能够在 Gewechat 适配器下正确发送表情包图片。

## 前提条件

- 一台具有公网 IP 的服务器
- 已安装 LangBot 和 Gewechat
- 基本的命令行操作能力

## 设置步骤

### 1. 创建表情包图片服务器

首先，我们需要创建一个 HTTP 服务器来托管表情包图片：

```bash
# 创建目录
mkdir -p /home/ubuntu/emoticon_server/images

# 复制表情包图片
cp -r /path/to/LangBot/plugins/EmoticonPlugin/images/* /home/ubuntu/emoticon_server/images/

# 创建服务器脚本
cat > /home/ubuntu/emoticon_server/server.py << 'EOF'
#!/usr/bin/env python3
import http.server
import socketserver
import os
import sys

# 设置服务器端口
PORT = 8000

# 获取当前目录作为服务器根目录
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        # 添加 CORS 头，允许所有来源访问
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

if __name__ == "__main__":
    # 创建服务器
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"Serving at http://0.0.0.0:{PORT}")
        try:
            # 启动服务器
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
            sys.exit(0)
EOF

# 添加执行权限
chmod +x /home/ubuntu/emoticon_server/server.py
```

### 2. 创建 systemd 服务单元文件

为了确保表情包图片服务器能够随系统自启动，我们创建一个 systemd 服务单元文件：

```bash
# 创建服务单元文件
cat > /home/ubuntu/emoticon-server.service << 'EOF'
[Unit]
Description=Emoticon HTTP Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/emoticon_server
ExecStart=/usr/bin/python3 /home/ubuntu/emoticon_server/server.py
Restart=always
RestartSec=5
StartLimitInterval=0

[Install]
WantedBy=multi-user.target
EOF

# 安装服务单元文件
sudo cp /home/ubuntu/emoticon-server.service /etc/systemd/system/

# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 启用并启动服务
sudo systemctl enable emoticon-server.service
sudo systemctl start emoticon-server.service
```

### 3. 配置防火墙

确保服务器防火墙允许访问表情包图片服务器的端口：

```bash
# 开放 8000 端口
sudo ufw allow 8000/tcp

# 重新加载防火墙规则
sudo ufw reload
```

### 4. 配置表情包插件

编辑表情包插件的配置文件：

```bash
# 创建或编辑配置文件
cat > /path/to/LangBot/plugins/EmoticonPlugin/config.json << EOF
{
  "url_prefix": "http://你的公网IP:8000/images",
  "use_url": true,
  "emoticons": []
}
EOF
```

请将 `你的公网IP` 替换为您服务器的实际公网 IP 地址。

### 5. 重启 LangBot 服务

```bash
# 如果使用 Docker
sudo docker restart langbot

# 如果直接运行
# 重启您的 LangBot 服务
```

## 验证设置

设置完成后，您可以通过以下方式验证表情包 URL 功能是否正常工作：

1. 访问 `http://你的公网IP:8000/images/愉快.gif`（替换为实际的表情包文件名），确认能够正常显示图片
2. 与微信机器人对话，尝试让 AI 使用表情包，例如问："你能用愉快的表情回复我吗？"
3. 检查 LangBot 日志，确认是否有 "发送表情包 URL" 和 "已发送表情图片 URL" 的日志记录

## 常见问题排查

### 问题 1：表情包无法发送，日志显示"未找到表情"

**解决方法**：
1. 检查表情包文件名是否正确
2. 检查表情包是否已复制到 `/home/ubuntu/emoticon_server/images/` 目录
3. 重启 LangBot 服务

### 问题 2：表情包能找到但无法显示图片

**解决方法**：
1. 检查表情包图片服务器是否正常运行：`sudo systemctl status emoticon-server.service`
2. 检查防火墙是否允许访问 8000 端口：`sudo ufw status`
3. 尝试从外部网络访问表情包图片 URL，确认是否可以访问

### 问题 3：系统重启后服务没有自动启动

**解决方法**：
1. 检查服务是否已启用：`sudo systemctl is-enabled emoticon-server.service`
2. 如果未启用，执行：`sudo systemctl enable emoticon-server.service`
3. 手动启动服务：`sudo systemctl start emoticon-server.service`

## 安全建议

1. 考虑为表情包图片服务器添加基本的身份验证
2. 限制只允许 LangBot 服务器的 IP 访问表情包图片服务器
3. 定期更新服务器系统和软件包
