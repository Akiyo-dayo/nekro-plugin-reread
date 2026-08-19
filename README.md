# NekroAgent 复读姬

[更新日志](CHANGELOG.md) · 当前版本 **1.0.0**

群友开始复读时，机器人会蹲在旁边：到阈值就按概率**跟读**或**打断**。文本、图片、表情分开计数，冲着群里好玩来的，不是严肃风控插件。

玩法参考过 [astrbot_plugin_reread](https://github.com/Zhalslar/astrbot_plugin_reread)，但判定模型和互动是按 NekroAgent 重写的，不是移植。

## 玩法

- 同一句文本 / 同一张图 / 同一个表情连续出现，分别用自己的阈值。
- 达到阈值后先掷**打断概率**，没打断再掷**复读概率**。
- 默认要**不同人接力**，一个人连刷带不动复读姬。
- 跟读或打断时，默认**拦住 AI**：消息仍记入历史，但不叫醒 Agent，避免它跟着起哄。
- 屏蔽词、屏蔽人、群白名单 / 黑名单、冷却、过长文本、指令、@ 机器人，都可以挡。
- 今日复读榜：谁最爱接话。

判定顺序：**禁言（默认关）→ 打断 → 复读 → 什么都不做**。这一波没掷中的话，下一句同样内容会再掷一次。同一条内容刚被跟读/打断过，不会立刻再打一遍；换一条再复读才行。

## 指令

命令前缀以你的 NekroAgent 配置为准，下面以 `/` 为例：

| 指令 | 别名 | 说明 |
| --- | --- | --- |
| `/reread` | `/复读姬` | 本群开关、当前连击、今日复读王 |
| `/reread_stats` | `/复读榜` `/今日复读王` | 今日复读榜 |
| `/reread_help` | `/复读姬帮助` | 帮助 |
| `/reread_on` | `/开启复读姬` | 超管：开本群 |
| `/reread_off` | `/关闭复读姬` | 超管：关本群 |
| `/reread_reset` | `/重置复读` | 超管：清空连击窗口 |

## 安装

把仓库里的 **`reread` 文件夹** 复制到 NekroAgent 工作插件目录，目录名必须是 `reread`：

```text
<nekro-agent>/plugins/workdir/reread/
  __init__.py
  plugin.py
  engine.py
  ...
```

不要把带连字符的整个仓库目录直接丢进 `workdir`，Python 无法导入 `nekro-plugin-reread`。

```bash
git clone https://github.com/Akiyo-dayo/nekro-plugin-reread.git
```

Linux / macOS：

```bash
cp -r nekro-plugin-reread/reread <nekro-agent>/plugins/workdir/reread
```

Windows PowerShell：

```powershell
Copy-Item -Recurse .\nekro-plugin-reread\reread <nekro-agent>\plugins\workdir\reread
```

然后在 WebUI 启用插件「复读姬」。目前按 `onebot_v11` 群聊接入，表情跟读和禁言依赖 OneBot。

## 配置

| 项 | 默认 | 说明 |
| --- | --- | --- |
| 文本 / 图片 / 表情开关 | 开 | 可单独关掉某一类 |
| 文本阈值 | 3 | 同一句话出现几次后才可能动手 |
| 图片阈值 | 3 | 同一张图 |
| 表情阈值 | 2 | QQ 系统表情、表情包 |
| 复读概率 | 0.72 | 没被打断时跟读的概率 |
| 打断概率 | 0.18 | 达到阈值后先掷这个 |
| 必须不同人 | 开 | 防单人带节奏 |
| 冷却秒数 | 8 | 动手后消停一会儿 |
| 复读时拦 AI | 开 | 跟读/打断时不叫醒 Agent |
| 屏蔽词 / 屏蔽 QQ | 空 | 命中则不参与 |
| 群白名单 | 空 | 填了就只在这些群上班 |
| 群黑名单 | 空 | 这些群永不复读 |
| 打断文案 | 空 | 留空用内置吐槽池，可用 `{combo}` |
| 禁言概率 | 0 | 默认关。需要管理员权限 |

## 给 AI 的能力

群聊中 AI 可调用「查看复读榜」，拿到今日排名后再用一两句吐槽。复读姬自己动手时默认不叫醒 Agent。

## 开发

```bash
python -m pytest tests -q
```

解析、连击窗口、概率和屏蔽逻辑不依赖 NekroAgent，可单独跑测试。

## 致谢

- [KroMiose/nekro-agent](https://github.com/KroMiose/nekro-agent) 插件接口
- [Zhalslar/astrbot_plugin_reread](https://github.com/Zhalslar/astrbot_plugin_reread) 玩法参考（非移植）
