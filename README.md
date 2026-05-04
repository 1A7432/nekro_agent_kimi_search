# Kimi 联网搜索插件

基于 Moonshot AI Kimi 模型内置 `$web_search` 工具的 Nekro Agent 第三方联网搜索插件。

## 功能

为 AI 提供联网搜索能力，获取实时信息。

## 安装

1. 将插件文件夹复制到 Nekro Agent 的 `plugins/workdir/` 目录下
2. 重启 Nekro Agent 或重载插件
3. 在插件配置页面中配置 Moonshot AI API Key

## 配置

- **API Key**: Moonshot AI API 密钥（必填）
- **模型**: 推荐使用 `kimi-k2.6`（支持长上下文，适配 `$web_search`）
- **搜索冷却时间**: 防止重复搜索的间隔时间（秒）
- **最大返回 Token 数**: 搜索结果的最大 Token 数量

> **注意**：`kimi-k2.6` 使用 `$web_search` 时 `temperature` 固定为 `0.6`，无需也不支持自定义。

## API Key 获取

访问 [Moonshot AI 开放平台](https://platform.moonshot.ai/) 注册并获取 API Key。

## 费用

每次联网搜索收取 ￥0.03（由 Moonshot AI 收取）。

## 许可证

MIT License

---

作者: dirac  
版本: v0.1.1
