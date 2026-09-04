# PDF 转 Word 网页工具

一个带访问密码的网页程序，可将文字型、扫描型或混合型 PDF 转换成优先可编辑的 DOCX。普通页面直接提取文字，扫描页面自动使用 Tesseract OCR。支持本机、局域网和 Render 公网部署。

## 环境要求

- Python 3.10 或更高版本
- Tesseract OCR 5.x
- Tesseract 简体中文和英文语言包

Ubuntu / Debian 可执行：

```bash
sudo apt-get update
sudo apt-get install python3-venv tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng
```

确认 OCR 语言包：

```bash
tesseract --list-langs
```

输出中应包含 `chi_sim` 和 `eng`。

## 安装

```bash
cd /home/zhangwz/pdf
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 启动

```bash
./run.sh
```

本地默认访问密码为 `local-dev-password`，仅用于开发测试。也可以设置自己的本地密码和会话密钥：

```bash
APP_PASSWORD='你的本地访问密码' SESSION_SECRET='至少32个字符的随机字符串' ./run.sh
```

本机浏览器打开：<http://127.0.0.1:8000>

服务默认只监听本机。允许同一局域网的其他设备访问时，必须同时设置自定义密码和随机会话密钥：

```bash
HOST=0.0.0.0 APP_PASSWORD='自定义密码' SESSION_SECRET='至少32个字符的随机字符串' ./run.sh
```

其他设备随后可使用服务器 IP 访问，例如：<http://192.168.1.219:8000>。

如需更换端口：

```bash
PORT=8080 ./run.sh
```

如需明确只允许本机访问：

```bash
HOST=127.0.0.1 ./run.sh
```

## 使用

1. 输入访问密码。
2. 拖入或选择一个不超过 30 MB、100 页的 PDF。
3. 点击“开始转换”。
4. 等待页面显示转换进度。
5. 转换完成后下载 DOCX。

下载完成后，服务会清理该任务的临时文件。超过一小时的遗留任务目录会在服务重启或清理任务执行时移除。

## 测试

```bash
.venv/bin/python -m pytest -v
```

测试覆盖上传校验、任务隔离、文字提取、扫描件 OCR、DOCX 生成、API 和网页资源。

## Docker 自测

```bash
docker build -t pdf-to-word:local .
docker run --rm -p 10000:10000 \
  -e APP_ENV=production \
  -e APP_PASSWORD='自行设置的测试密码' \
  -e SESSION_SECRET='自行生成的至少32字符随机字符串' \
  pdf-to-word:local
```

访问 <http://127.0.0.1:10000/health>，应返回 `{"status":"ok"}`。

## 免费公网部署到 Render

1. 将项目推送到 GitHub。`说明.txt`、`.env`、上传文件和生成文件已被忽略，不要强制添加。
2. 登录 Render，选择 **New → Blueprint**，连接 GitHub 仓库并选择本项目的 `render.yaml`。
3. 在 Render 环境变量页面填写 `APP_PASSWORD`，供使用者登录。
4. 为 `SESSION_SECRET` 填写至少 32 字节的随机值，可用 `openssl rand -hex 32` 在自己终端生成；不要把结果发到聊天或写入仓库。
5. 部署完成后访问 Render 提供的 `https://...onrender.com` 地址。

免费实例一段时间无人访问后会休眠，首次打开可能需要约一分钟；重新部署或重启会清除进行中的转换任务。文件仅保存在临时文件系统，下载完成或超过一小时后清理。

生产模式必须同时提供 `APP_PASSWORD` 和长度不少于 32 字符的 `SESSION_SECRET`，否则应用会拒绝启动。公网默认限制为 30 MB、100 页、1 个执行任务和 1 个等待任务。

## 转换说明

- 输出目标是文字、段落和表格可编辑，不保证与 PDF 像素级一致。
- PDF 有可用文本层时不会重复 OCR，以减少错字。
- 扫描页分别尝试简体中文和英文 OCR，并根据识别结果选择更合适的内容。
- 复杂多栏、公式、手写文字、印章、艺术字体和质量较差的扫描件可能需要人工校对。
- 加密 PDF 需要先移除密码。

## 常见问题

如果页面提示 OCR 失败，请确认：

```bash
tesseract --version
tesseract --list-langs
```

如果缺少中文语言包，在 Ubuntu / Debian 上安装：

```bash
sudo apt-get install tesseract-ocr-chi-sim
```
