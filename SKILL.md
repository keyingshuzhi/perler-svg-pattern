---
name: perler-svg-pattern
description: 轻量路由说明：本项目已改造为可安装的 MCP 服务包。将图片转换为可制作拼豆 SVG、查询实体色板或校验拼豆 SVG 时，调用 MCP 工具，不要把完整图像处理流程塞入 Skill 提示词。
---

# Perler SVG Pattern MCP 路由

本项目的生产接口是 `perler_svg_pattern.mcp_server`（包内模块），不是厚重的对话 Skill。客户端通过
MCP 工具调用确定、可测试的处理链路；源码图片保持原位，产物写入调用者明确
指定的输出目录。

维护团队：柯影数智团队。

## 安装与启动

```bash
# 方式一：uvx 一键启动（推荐）
uvx perler-svg-pattern

# 方式二：pip 安装
pip install perler-svg-pattern
python -m perler_svg_pattern

# 方式三：魔塔容器部署
docker compose up -d
```

## 工具路由

| 用户目标 | MCP 工具 |
| --- | --- |
| 查询支持的 Perler / Hama / Artkal 色板 | `list_brand_palettes` |
| 查看某个品牌色板的真实色号、名称和 HEX 参考 | `get_brand_palette` |
| 将图片生成可拼制 SVG 图纸、购物清单与报告 | `convert_image` |
| 校验已有 SVG 是否为合格拼豆矢量图纸 | `validate_svg_artifact` |

## 调用准则

- 生成图纸时优先调用 `convert_image`，并提供已有的 `input_path` 与明确的 `output_dir`。
- 要严格匹配可购买颜色时，先调用 `list_brand_palettes`，再将返回的 palette 名称传给 `convert_image.brand`。
- 人物、宠物、Logo、风景、插画分别使用 `portrait`、`pet`、`logo`、`landscape`、`art` / `illustration` 模式；未确定时使用 `auto`。
- 需要验证交付物时调用 `validate_svg_artifact`。转换工具本身也会在成功返回前完成完整的图纸校验。
- 不要复制输入图到服务器目录，也不要要求模型手工重述主体识别、量化、清理或 SVG 生成流程；这些都是 MCP 服务端实现的职责。

## 完整部署指南

详见 [README.md](README.md) 和 [DEPLOY.md](DEPLOY.md)。