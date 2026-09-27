# Beyond Words — 项目总纲与 Agent 开发说明

> **English is more than words.**  
> 项目定位：基于可穿戴录音设备的真实英语会话行为分析与反馈系统。  
> 当前阶段：Mobile-first Web App + 虚拟录音豆；取得实体 soundcore Work 3200 后再接入官方 SDK。  
> 文档性质：产品需求、UI 规范、技术架构、数据契约、MVP 验收和开发优先级的统一依据。

## 0. 给开发 Agent 的总指令

请按本文开发一个**可运行**的移动端优先 Web MVP。核心目标：用户录制一段真实双人英语交流，标记一个值得复盘的时刻；系统生成带时间戳的转写、双人话轮时间轴和有原声证据的互动反馈；用户可回听片段、完成针对性练习并保存结果。

**产品研究对象是英语会话互动能力（interactional competence）：话轮转换、回应时机、话题延续、澄清与交流修复。** 语法纠错、单词卡、传统听力复习卡可作为辅助，但不要让它们取代核心产品。

初赛没有实体硬件：使用浏览器麦克风和虚拟录音豆完成端到端演示；UI 必须标注 **Simulator**。任何尚未验证的 Soundcore SDK 功能均作为后续适配项。演示数据须标为 Mock，不得冒充真实模型输出。

**实现顺序：移动端 UI 骨架 → 真实录音及标记 → 音频上传/保存 → ASR/说话人区分/话轮时间轴 → Topic Development 互动事件分析 → 原声反馈 → 简单练习。** 遇到复杂模型或外部凭证阻塞时，保留真实音频流程，使用清楚标记的 Mock 分析数据，并持续完成可运行系统。

---

## 1. 产品与用户

### 1.1 一句话定义

Beyond Words 帮助英语学习者理解自己**如何参与真实对话**，对实际发生的互动进行有证据的复盘，并在相似情境中练习新的交际策略。

核心闭环：

```text
真实英语交流 → 录音与重点标记 → ASR/说话人/话轮分析
→ 互动事件识别 → 证据可追溯的反馈 → 情境练习 → 下一次交流验证
```

### 1.2 目标人群与首版场景

- 有一定英语基础、但在真实交流中难以顺利接话、提问或延续话题的学习者。
- 英语角、英文小组讨论、课堂交流、留学生活、英语面试等场景。
- **首版限定安静环境的双人英语交流**；多人对话属于扩展范围。

典型困难：回答后话题结束、难以发起追问、回应前需要组织语言、发生重叠时不知如何衔接、没听清时不会请求澄清、难以修复误解。

### 1.3 与普通录音学习工具的区别

主要分析对象是**完整对话的时间结构和交际行为序列**，而非单独的难词、连读或听不懂的句子。一次互动事件应包括前后相关话轮、发生时间、原声、客观观察、谨慎解释和可练习的替代策略。

> 描述性数据不能直接当作好坏评价：说话占比低、停顿长、回答简短，均需结合任务、语境、个人习惯和对话伙伴判断。

---

## 2. 核心创新与研究主线

1. **会话动态分析（Conversation Dynamics）**：保留时序信息，分析发言时间、话轮、回应间隔、重叠发言与交际行为。
2. **上下文互动事件发现（Interaction Insights）**：例如“对方开放提问 → 用户简短回答 → 话题结束”，提供对应原声与前后语境；避免把短回答一律判为错误。
3. **物理标记驱动的事件定位**：标记表示“这一段交流值得回头分析”。算法根据时间戳与话轮边界扩大范围，不机械地截取固定前后 20 秒。
4. **真实情境迁移练习**：在保留原始交际目标的同时改写场景或问法，训练延续话题、追问和请求澄清。

推荐研究问题：如何从可穿戴设备记录的连续英语语音中，识别可复盘的互动事件，并生成上下文一致、证据可追溯的交际策略反馈？

---

## 3. 产品信息架构

底部四个 Tab：**Home / Review / Practice / Profile**。额外核心页面：**Recording / Moment Detail**。

| 页面 | 用户要完成的事情 | 关键组件 |
|---|---|---|
| Home | 查看设备、开始交流、继续未完成的复盘 | 设备卡、录音入口、统计、历史会话 |
| Recording | 真实录音、查看状态、标记互动时刻 | 虚拟录音豆、实况波形、计时、标记列表 |
| Review | 查看一次交流怎样展开 | 会话摘要、指标、双轨时间轴、Insight 卡 |
| Moment Detail | 回到具体事件并理解可尝试的策略 | 原声片段、相关话轮、观察/解释/建议 |
| Practice | 练习具体交际策略 | Replay、Strategy Challenge、回答反馈 |
| Profile | 查看历史、目标与训练记录 | 会话历史、完成的练习、个人目标 |

### 3.1 Home 首页

- 品牌、问候语、个人入口；设备状态明确为 `Simulator / Computer or phone microphone ready`。
- 主入口 `Start a Conversation`，配蓝色大卡片和一句简洁引导：`Every conversation is a chance to grow.`
- 本周统计：Conversations、Speaking Time、Marked Moments、Practiced；均由真实记录计算。
- 最近会话：标题、日期、时长、人数、标记数、分析状态，点击进入 Review。
- 不伪造设备蓝牙连接、电量等真机数据。

### 3.2 Recording 录音页

录音豆模拟一个按钮：

| 状态与操作 | 行为 |
|---|---|
| 待机单击 | 开始录音 |
| 录音中单击 | 停止录音 |
| 录音中双击 | 添加标记，录音继续 |
| 待机双击 | 不创建标记 |
| 无麦克风权限或录音失败 | 显示错误，不能假装开始录音 |

**单/双击判定窗口约 250–300 ms**，必须防止双击先触发单击停止录音。为移动端易用性，可同时提供单独的“标记”和“停止”辅助按钮。页面展示：录音状态、实时音频波形、实际音频时长、麦克风权限、场景选择、已创建的标记及时间戳、明确的退出与保存状态。

场景选项：Casual Conversation / English Corner / Group Discussion / Classroom / Interview / Other。首版默认 Casual Conversation。

标记成功反馈：`Moment saved · 02:14`。标记含义统一为“这段互动值得复盘”，不要自动宣称“用户没听懂”。

结束录音后展示时长、标记数、保存状态和 `Analyze Conversation`；后台处理状态显示为 `Saved → Transcribing → Analyzing → Ready`。失败可重试，必须保留已成功保存的原始音频。

### 3.3 Review 会话报告

**Conversation Summary**：主题、说话人数量、主要话题、可复盘事件；不可编造原文外的事实。

**Conversation Dynamics**：

| 指标 | 解释 |
|---|---|
| Speaking Time | 目标用户实际发言的时长 |
| Speaking Share | 用户发言时长占全部发言时长的比例 |
| Response Gap | 伙伴一轮结束到用户下一轮开始的间隔，优先中位数及分布 |
| Turn Count | 用户话轮数 |
| Question Count | 用户主动提问次数 |
| Clarification Count | 请求澄清次数 |
| Overlap Events | 与他人同时发言的事件数 |

**Conversation Timeline**：横轴时间、纵轴 Speaker。蓝色用户话轮、绿色伙伴话轮、黄色待核查重叠区域、橙色菱形标记、灰色非语音区域。支持横向滚动、点击话轮播放、点击标记跳转事件详情。首版可固定比例，不强求复杂缩放。

**Interaction Insights** 首版先支持 `TOPIC_DEVELOPMENT`；后续增加 `RESPONSE_TIMING`、`CLARIFICATION_REPAIR`、`PARTICIPATION`。每条卡片包含类型、原声音频范围、关联话轮、观察、解释、不确定性、替代策略和练习入口。

### 3.4 Moment Detail 事件详情

示例：

```text
A: What do you think about this idea?
You: Yeah, it's good.
A: Okay...
```

展示：
- 原声音频片段及可点击时间戳；
- 前后必要话轮和用户重点标记；
- **What happened**：对方邀请表达意见，用户简短表示赞同，话题随后结束；
- **Try another approach**：`I like the idea because it could save us time. What do you think?`；
- **Why this may help**：补充理由并邀请伙伴继续参与；
- `Practice this moment`。

建议语言使用“如果你希望继续这个话题，可以……”等语境化表达；不输出未经验证的英语能力总分，也不推测性格、动机或心理状态。

### 3.5 Practice 练习页

首版实现两种：

- **Conversation Replay**：保持原始交际目标，替换场景或问题，例如从讨论电影之夜迁移到讨论周末学习小组；支持语音回答和文字兜底。
- **Strategy Challenge**：`Extend a Topic`、`Ask a Follow-up`、`Ask for Clarification`、`Join a Discussion`。初赛优先前两项或 `Topic Development + Clarification`。

反馈依据：是否表达观点、补充相关信息、符合交流目的、自然邀请对方参与。接受多种合理答案。保存原任务、答复、反馈、时间及关联事件。

### 3.6 Profile 我的

- 会话历史、互动模式、训练历史、个人交际目标。
- 目标可选：延续话题、主动提问、参与小组讨论、请求澄清。
- 通过相似任务中的重复观察和练习结果反映进步，不根据单次对话生成虚假综合能力分。

---

## 4. UI / UX 规范

**风格：** Clean / Modern / Human-centered / Audio-first / Educational。浅色内容界面 + 深色沉浸式录音页；手机端具有接近原生 App 的完成度。

| 用途 | 色值 |
|---|---|
| 主品牌蓝 | `#2563EB` |
| 深蓝 | `#1D4ED8` |
| 页面背景 | `#F8FAFC` |
| 主文字 | `#0F172A` |
| 次文字 | `#64748B` |
| 卡片 | `#FFFFFF` |
| 用户话轮 | `#3B82F6` |
| 伙伴话轮 | `#22C55E` |
| 标记 | `#F59E0B` |
| 录音状态 | `#EF4444` |
| 录音页背景 | `#0B1220` |

- 移动端以 390px 视口为主要设计基准，兼容 360/375/430px；桌面端可居中展示手机布局。
- 大圆角卡片、清楚的排版层级、足够留白、可触摸的按钮区、固定底部导航。
- 优先打磨五个视觉组件：`VirtualBean`、`AudioWaveform`、`ConversationTimeline`、`InsightCard`、`PracticeCard`。
- 波形必须响应真实输入，静音时不能一直展示装饰性动态波形。
- 视频/演示/截图中的模拟设备与模型结果均需明确标注。

---

## 5. 技术架构与工程边界

```text
Mobile-first React Web App
  └─ Recording Adapter
       ├─ WebSimulator: browser microphone + UI button (initial)
       └─ SoundcoreAdapter: native SDK bridge (future, subject to actual API)
  └─ Audio + markers with shared session timebase
       └─ FastAPI / audio storage / processing job
            └─ ASR with timestamps
                 └─ speaker diarization + alignment
                      └─ turn segmentation + timeline
                           └─ dialogue-act classification
                                └─ contextual interaction insights
                                     └─ replay / strategy practice
```

原始建议栈：React + TypeScript + Vite + Tailwind CSS + React Router + Zustand + Lucide；浏览器 `getUserMedia`、`MediaRecorder`、Web Audio API；Python FastAPI；SQLite 起步，音频文件本地保存；语音识别、VAD、说话人分离与结构化 LLM 分析。当前企业实现已经固定为 PostgreSQL、对象存储、千问唯一语音 Provider 与 DeepSeek 语义模型，详见根目录 `README.zh-CN.md`。

依赖应可替换；若第三方 API 密钥或权重不可用，提供显式 Mock 分析模式，**真实录音与保存仍须可用**。

### 5.1 Web 端限制

- 手机用手机麦克风，电脑用电脑麦克风；上传到后端后才由后端保存，网页不能直接写入电脑任意目录。
- 手机访问麦克风通常需要安全上下文：localhost 或 HTTPS；普通局域网 HTTP 在手机端可能失败。
- 移动浏览器切后台、锁屏时录音可能中断；初赛演示保持前台并检测实际录音状态。PWA 安装不保证后台持续录音。
- 录音分片持久化、异常恢复和时钟/采样率校准应考虑长时间使用。

### 5.2 录音适配接口（概念契约）

```ts
interface RecorderAdapter {
  startRecording(): Promise<void>;
  stopRecording(): Promise<RecordingResult>;
  markMoment(): void;
  getStatus(): RecorderStatus;
}
```

未来 `SoundcoreAdapter` 是否能逐项实现，取决于实际 SDK 的标记时间戳、文件与实时音频等接口。不要假设浏览器能直接调用 Android/iOS 原生 SDK；可使用原生桥接或后续独立移动 App。

---

## 6. AI Pipeline 与数据约束

### A. 采集与统一时间基准

音频、时间戳和标记必须绑定同一个会话。按音频帧数、采样率和实际录音时间校准，避免长录音标记漂移。

```json
{
  "session_id": "session_001",
  "duration_ms": 180000,
  "markers": [{"id": "marker_001", "timestamp_ms": 43000}]
}
```

### B. ASR

英语转写必须有时间戳；允许用户修正错误。保存模型/服务名称、处理状态和失败原因；置信信息只在模型真实提供且可解释时使用。

```json
{"start_ms": 12400, "end_ms": 15600, "text": "What do you think about this idea?"}
```

### C. Speaker diarization 与 turn segmentation

首版双人，用户分析后确认“哪个 Speaker 是我”。模型输出与 ASR 需时间对齐；若重叠语音不能可靠识别，标记待核查，不强制归一个说话人。

```json
{
  "turn_id": "turn_001",
  "speaker_id": "SPEAKER_00",
  "start_ms": 12400,
  "end_ms": 15600,
  "text": "What do you think about this idea?"
}
```

### D. Dialogue Act Recognition

首版标签：

```text
QUESTION, ANSWER, FOLLOW_UP, OPINION, AGREEMENT,
DISAGREEMENT, CLARIFICATION_REQUEST, CLARIFICATION_RESPONSE,
CONFIRMATION, TOPIC_INITIATION, TOPIC_CONTINUATION, OTHER
```

允许单话轮多标签；识别需使用前后话轮语境。

### E. Interaction event detection

初赛优先 `TOPIC_DEVELOPMENT`，后续再做 `RESPONSE_TIMING`、`CLARIFICATION_REPAIR`、`PARTICIPATION`。

```json
{
  "event_id": "event_001",
  "type": "TOPIC_DEVELOPMENT",
  "start_ms": 12000,
  "end_ms": 23000,
  "turn_ids": ["turn_001", "turn_002", "turn_003"],
  "marker_ids": ["marker_001"],
  "confidence": null
}
```

没有真实计算/校准方法时不要让 LLM 编造精确 `confidence` 数字。

### F. 证据可追溯反馈

```json
{
  "event_type": "TOPIC_DEVELOPMENT",
  "observation": "The user gave a brief response.",
  "context": "The partner asked for an opinion.",
  "suggestion": "If the user wants to continue, add a reason or ask a follow-up question.",
  "example": "I think it's a good idea because...",
  "evidence_turn_ids": ["turn_001", "turn_002"]
}
```

严格区分**观察事实 / 语境解释 / 可选建议**；解释须关联真实音频和话轮，允许模型表示不确定性。

---

## 7. 数据模型与后端 API

建议实体：

| 实体 | 必要字段 |
|---|---|
| Session | id、title、scenario、duration、processing_status |
| AudioAsset | location、format、sample_rate、duration |
| Marker | id、session_id、timestamp_ms |
| Speaker | id、session_id、user_confirmed_identity |
| Turn | id、speaker_id、start_ms、end_ms、text |
| DialogueAct | turn_id、labels |
| InteractionEvent | type、start/end、turn_ids、marker_ids |
| Insight | observation、context、suggestion、evidence |
| Practice | type、prompt、source_event_id |
| PracticeAttempt | response、feedback、time |

建议 REST 接口：

```text
POST   /api/sessions
GET    /api/sessions
GET    /api/sessions/{id}
POST   /api/sessions/{id}/audio
POST   /api/sessions/{id}/markers
POST   /api/sessions/{id}/analyze
GET    /api/sessions/{id}/status
GET    /api/sessions/{id}/analysis
PATCH  /api/sessions/{id}/speakers
PATCH  /api/sessions/{id}/turns
GET    /api/events/{id}
GET    /api/events/{id}/audio
POST   /api/events/{id}/practice
POST   /api/practice/{id}/attempts
DELETE /api/sessions/{id}
```

分析作为后台任务执行：提交后返回状态，前端轮询或订阅结果；失败可重试、原音保留、避免重复会话/标记。

---

## 8. 研发优先级与验收

### P0：初赛必须真实可运行

- [ ] 手机/电脑均可访问移动端 Web。
- [ ] 虚拟录音豆单击开始/停止，双击标记时录音不中断。
- [ ] 麦克风真实采集、波形响应实际输入、音频可播放/保存。
- [ ] 重点标记能对应音频时间轴。
- [ ] 音频上传并进入处理队列。
- [ ] 英语 ASR 生成带时间戳的转写。
- [ ] 双人说话人区分与用户身份确认。
- [ ] 两轨话轮时间轴和原声片段播放。
- [ ] 至少检测一种 `TOPIC_DEVELOPMENT` 事件。
- [ ] 生成基于原话轮的观察/解释/策略反馈。
- [ ] 保存会话，刷新后可以重新打开。

### P1：核心跑通后

Response Timing、Clarification & Repair、重叠语音、手动时间轴修正、练习及记录、历史趋势、删除/导出。

### P2：后续扩展

多人讨论、连续语音角色扮演、跨会话个性化模式、复杂交际行为模型、离线 PWA、SDK 真机接入与音频大规模存储。

### 可核查的测试与指标

| 模块 | 指标/方法 |
|---|---|
| ASR | WER |
| 说话人分离 | DER，注明标注和评测范围 |
| 话轮边界 | 时间误差/边界 F1，明确容差 |
| 交际行为和事件 | Precision、Recall、F1 |
| 事件定位 | 区间 IoU 或起止边界误差 |
| AI 反馈 | 证据一致性、人评准确性和实用性 |
| 产品体验 | 处理时延、标记定位成功率、回听可达性 |

数据集优先由队员及知情同意的参与者录制双人英语对话，人工标注问答、追问、简短回答、澄清、长停顿、重叠与话题切换。展示时说明测试规模和误差；短时 Demo 只能验证闭环，不能单独证明长期学习效果。

---

## 9. 初赛演示脚本

1. 在手机网页选择 Casual Conversation，展示明确的 Simulator 状态。
2. 两名队员用英语讨论英文电影之夜：`What do you think about organizing an English movie night?` → `Yeah, sounds good.` → `Okay, what kind of movies do you like?`
3. 用户双击虚拟录音豆，标记一个想回顾的互动位置；继续聊几句后停止。
4. 展示真实保存的音频、转写、说话人身份确认和两轨话轮时间轴。
5. 点击重点标记，展示 `Topic Development` 事件及上下文原声。
6. 查看反馈：如果想进一步讨论，可以补充理由或主动追问。
7. 打开新的相似场景练习，例如 `What do you think about having a study group every weekend?`，用户回答并获得反馈。
8. 保存练习与会话历史。

Demo 必须清楚展示 **完整语音时间序列 → 互动行为 → 可回听证据 → 交际策略训练**，与普通英语单句复习卡形成区别。

---

## 10. 隐私、安全与准确性

- 真实英语交流涉及其他人的声音：录音前提醒取得参与者知情同意，并展示录音状态。
- 默认用户主动开启录音；初赛不做后台持续监听。
- 解释音频上传、ASR/LLM 处理方式；提供音频和会话删除。
- 尽可能避免在后端日志记录完整录音/敏感原文。
- 页面后台或锁屏造成录音中断时要明确提示，不继续假装录音。
- Mock 模式、虚拟设备、演示数字与真实分析必须区分。
- 不推断用户心理、人格或交流伙伴意图；不把长停顿、简短回答和说话占比直接判为缺陷。

---

## 11. 开发里程碑与交付

**Milestone 1：UI 骨架**  
项目初始化、路由、底部导航、6 个页面、统一主题与显式 Mock 数据。

**Milestone 2：真实录音**  
权限、实况波形、计时、单/双击、标记、音频保存/播放、异常处理。

**Milestone 3：会话结构**  
后端上传、ASR、双人说话人区分、时间对齐、身份确认和时间轴。

**Milestone 4：互动反馈**  
Topic Development、音频证据、观察与解释、策略建议。

**Milestone 5：练习和端到端演示**  
相似情境练习、作答、结果保存、部署与测试。

**最终交付物：** 前后端源码、README（本地启动与部署步骤）、环境变量示例、数据模型说明、必要测试、可复现的端到端演示与明确标注的 Mock 备用模式。

**完成定义：** 用户能在真实手机或电脑浏览器完成“录一段双人英语对话 → 双击标记 → 分析 → 查看双方话轮和互动事件 → 回听原声 → 获得有依据的策略反馈 → 完成练习 → 再次查看记录”。

---

## 12. 项目摘要（可用于参赛材料）

**Beyond Words — English is more than words.**

Beyond Words 是基于可穿戴录音设备的真实英语会话行为分析与反馈系统。系统以真实英语对话为对象，结合语音时序分析、说话人分离、话轮分割、交际行为识别与大语言模型，识别话题延续、回应时机、交际修复和讨论参与等互动事件。用户可通过录音豆的重点标记选择值得复盘的时刻；移动端 App 将事件与原始音频和前后话轮关联，生成可核查的反馈和情境练习。初赛采用 Mobile-first Web App 与虚拟录音豆展示完整闭环，后续根据官方 SDK 能力接入实体 soundcore Work 设备。
