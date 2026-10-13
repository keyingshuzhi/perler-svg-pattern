# 部署指南：perler-svg-pattern MCP 服务

本项目提供三种部署方式，从本地开发到魔塔（ModelScope）生产部署均可覆盖。

## 方式一：uvx 一键启动（零安装，推荐用于快速体验）

要求系统已安装 `uv`（[安装说明](https://astral.sh/uv))：

```bash
# 直接运行内联元数据脚本
uv run uvx-perler-svg-pattern.py

# 或从 PyPI 拉取（需先发布到 PyPI）
uvx perler-svg-pattern
```

`uvx` 会自动创建一个临时虚拟环境、安装依赖并启动 MCP 服务器（stdio 传输）。无需提前 `pip install` 任何东西。

**MCP 客户端配置示例**（Claude Desktop / Cursor）：

```json
{
  "mcpServers": {
    "perler-svg-pattern": {
      "command": "uvx",
      "args": ["perler-svg-pattern"]
    }
  }
}
```

## 方式二：pip 安装后运行（适合固定环境）

```bash
# 安装包及其依赖
pip install perler-svg-pattern

# 启动 MCP 服务器
python -m perler_svg_pattern

# 或使用安装的入口点
perler-svg-pattern
```

**MCP 客户端配置示例**：

```json
{
  "mcpServers": {
    "perler-svg-pattern": {
      "command": "python",
      "args": ["-m", "perler_svg_pattern"]
    }
  }
}
```

## 方式三：魔塔（ModelScope）容器化部署

### 3.1 构建镜像

```bash
docker build -t perler-svg-pattern:0.2.1 .
```

### 3.2 使用 docker-compose 启动

```bash
docker compose up -d
```

### 3.3 魔塔平台部署

魔塔支持将 MCP 服务作为 Docker 容器部署。在魔塔控制台中：

1. 选择「容器部署」或「MCP 服务」
2. 配置 Dockerfile 或使用 `docker-compose.yml`
3. 设置环境变量（如有）
4. 启动服务

**魔塔 MCP 客户端配置**：

```json
{
  "mcpServers": {
    "perler-svg-pattern": {
      "command": "docker",
      "args": ["exec", "-i", "perler-svg-pattern"]
    }
  }
}
```

### 3.4 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PYTHONUNBUFFERED` | `1` | 禁用 Python 输出缓冲，确保 MCP 协议消息实时传输 |
| `PYTHONDONTWRITEBYTECODE` | `1` | 禁止写入 `.pyc` 字节码文件 |
| `UV_LINK_MODE` | `copy` | uv 安装模式（copy vs hardlink） |

### 3.5 持久化存储

生成的 SVG 图纸、购物清单和 JSON 报告会写入 `/app/output`。在 `docker-compose.yml` 中已挂载到宿主机的 `./output` 目录：

```yaml
volumes:
  - ./output:/app/output:rw
```

## 产物规则（所有部署方式通用）

- 源图片永不复制到服务器包内
- 生成的 SVG 永不写入服务器包目录
- 中间文件使用内存或系统临时目录
- 用户产物属于当前工作空间或显式指定的路径

## 验证部署

```bash
# 检查包是否正确安装
python -c "import perler_svg_pattern; print(perler_svg_pattern.__version__)"

# 检查色板是否可加载
python -c "from perler_svg_pattern.scripts.palette import builtin_palette_names; print(builtin_palette_names())"

# 检查 MCP 服务器是否可启动
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python -m perler_svg_pattern
```