# 真实英语对话评测语料

本目录保存数据来源、许可和导入后的统一评测格式。原始音频与转写文件放在 `evaluation/raw/`，派生的短片段与 JSONL 放在 `evaluation/derived/`；两者都默认不提交到仓库。

## 已选数据

- **HCRC Map Task q1ec1**：公开的真实双人英语合作任务对话，包含自然追问、确认、澄清和简短回应；许可为 CC BY 4.0，作为立即可用的双人内容样本。
- **CANDOR**：1,600 多段真实双人视频对话，最贴合本项目的双人话轮、回应和话题延续评测。需要向原发布方登记申请，项目中只保存来源信息。
- **AMI ES2002a**：公开的英语会议音频、词级时间戳与说话人标注，许可为 CC BY 4.0。作为当前可立即运行的转写、话轮边界和说话人分离样本。
- **DiPCo**：四人自然晚餐对话，带近讲和远场阵列录音及人工转写，许可为 CDLA-Permissive；完整包约 13.4 GB，不默认下载。
- **CHiME-6**：真实家庭晚餐对话，但数据使用受许可约束，仅作为后续参考，不自动下载。

来源与机器可读字段见 `datasets.json`。

## 双人样本

```powershell
powershell -ExecutionPolicy Bypass -File evaluation/download_maptask_sample.ps1
python evaluation/import_maptask.py
```

导入结果位于 `evaluation/derived/hcrc-maptask-q1ec1/reference.json`。其中 `g` 表示路线说明者，`f` 表示路线跟随者。公开文本没有逐句时间戳，因此该样本用于内容、话轮顺序和交流策略评估；时间边界评估使用 AMI 标注。

## AMI 样本文件

执行：

```powershell
powershell -ExecutionPolicy Bypass -File evaluation/download_ami_sample.ps1
python evaluation/import_ami.py
```

如果 AMI 官方整包服务器速度过慢，也可以只下载 ES2002a 所需的四个词级 XML。脚本使用 CC BY 4.0 的 AMI 完整镜像作为传输源，并在本地解析校验 XML：

```powershell
powershell -ExecutionPolicy Bypass -File evaluation/download_ami_words.ps1
python evaluation/import_ami.py
```

若传输镜像不可达，可对官方整包使用经过长度和 ZIP 结构校验的并行 Range 下载：

```powershell
powershell -ExecutionPolicy Bypass -File evaluation/download_ami_annotations_parallel.ps1
powershell -ExecutionPolicy Bypass -File evaluation/download_ami_sample.ps1
python evaluation/import_ami.py
```

## 运行转写与说话人评估

模型输出可以是后端 `/api/sessions/{id}/analysis` 返回的 JSON，也可以是含有 `analysis` 字段的导出会话。统一评估命令：

```bash
python evaluation/transcribe_sample.py --audio evaluation/raw/maptask/q1ec1.mix.wav --output evaluation/derived/hcrc-maptask-q1ec1/prediction.json
python evaluation/evaluate.py --reference evaluation/derived/hcrc-maptask-q1ec1/reference.json --prediction evaluation/derived/hcrc-maptask-q1ec1/prediction.json --output evaluation/derived/hcrc-maptask-q1ec1/metrics.json
python evaluation/evaluate.py --reference evaluation/derived/ami-es2002a/reference.json --prediction prediction.json --output evaluation/derived/ami-es2002a/metrics.json
```

千问 Filetrans 评测会明确上传指定的公开评测音频。任务编号立即写入 checkpoint，命令中断后再次运行会继续轮询同一任务，不重复提交：

```powershell
python evaluation/transcribe_sample.py --language en --expected-speakers 2 --audio evaluation/raw/maptask/q1ec1.mix.wav --output evaluation/derived/hcrc-maptask-q1ec1/prediction-qwen.json
python evaluation/evaluate.py --reference evaluation/derived/hcrc-maptask-q1ec1/reference.json --prediction evaluation/derived/hcrc-maptask-q1ec1/prediction-qwen.json --output evaluation/derived/hcrc-maptask-q1ec1/metrics-qwen.json
```

输出包括：

- WER：英文转写词错误率、参考词数与编辑次数；
- DER：漏检语音、误检语音、说话人混淆以及最佳匿名说话人映射；
- 说话人帧准确率。当前轻量评分器以 100ms 为一帧，重叠语音只计一个活动说话人；对外发布前应再用独立标准评分器复核。

当前本机基线记录在 `baselines.json`：

- 历史本地基线（已归档）Map Task q1ec1：旧模型在 538 个参考词上得到 WER `0.2509`（135 次词编辑）；
- 历史本地基线（已归档）AMI ES2002a：旧模型在 2633 个规范化参考词上得到 WER `0.4151`（1093 次词编辑）。
- Qwen Audio 3.1 Filetrans（Map Task，转单声道，本轮复验）：识别 2 位说话人，WER `0.1952`，265 秒音频的端到端延迟约 `57.5s`；公开参考文本没有时间戳，因此不计算 DER。
- Qwen Audio 3.1 Filetrans（AMI ES2002a）：识别 4 位说话人，WER `0.3054`，简化 DER `0.3546`，说话人帧准确率 `0.8008`，1273 秒音频的端到端延迟约 `50.8s`。

这些结果用于发现回归，不代表最终模型上限。历史本地结果仅保留在 `baselines.json` 作为迁移前对照，不再进入默认运行、构建或测试。AMI 的人工时间戳和说话人参考已用于千问四人分离评分；正式报告仍建议用独立标准评分器复核重叠语音。

下载结果：

```text
evaluation/raw/ami/ES2002a.Mix-Headset.wav
evaluation/raw/ami/ami_public_manual_1.6.2.zip
evaluation/raw/ami/annotations/...
```

导入结果：

```text
evaluation/derived/ami-es2002a/reference.json
```

统一参考格式包含 `session_id`、`audio_path`、`license`、`speakers`、`turns`；每个话轮包含 `speaker_id`、`start_ms`、`end_ms` 和 `text`。后续评测代码只依赖这个统一格式，不绑定具体语料的原始目录结构。

## 使用边界

- 不把 CANDOR 或受许可约束语料重新分发到仓库。
- 保留数据集名称、来源链接和许可信息。
- 真实参与者音频只用于模型评测，不作为产品演示素材公开播放。
- 产品内采集的用户录音不能混入公共评测集。
