# 本地语音模型历史归档

归档日期：2026-09-26  
状态：不参与当前产品运行、构建、测试或生产部署。

## 归档原因

当前产品固定使用阿里云百炼 Qwen Audio 3.1：Filetrans 负责长录音转写和 1～8 人匿名说话人分离，Flash 负责短练习录音转写。旧的 `faster-whisper + pyannote Community-1` 本地链路退出默认产品，但保留源码和历史测试，便于未来评估私有化部署。

## 原路径与内容

| 归档文件 | 原路径 | 用途 |
|---|---|---|
| `backend/asr.py` | `backend/app/asr.py` | Whisper/faster-whisper 转写和 CPU/CUDA选择 |
| `backend/diarization.py` | `backend/app/diarization.py` | pyannote说话人分离与话轮归属 |
| `backend/speech_pipeline.py` | `backend/app/speech_pipeline.py` | 本地转写和分离组合流程 |
| `backend/model_setup.py` | `backend/app/model_setup.py` | 本地模型下载与初始化 |
| `backend/local_provider.py` | 原 `LocalSpeechProvider` | 历史 Provider适配器 |
| `deploy/Dockerfile.speech` | `backend/Dockerfile.speech` | 历史本地语音镜像 |
| `deploy/requirements-asr.txt` | `backend/requirements-asr.txt` | 历史模型依赖版本 |
| `tests/test_diarization.py` | `backend/tests/test_diarization.py` | 本地话轮归属测试 |
| `evaluation/transcribe_local_sample.py` | 原评测脚本的本地分支 | 历史本地基线入口 |
| `docs/build_legacy_solution_proposal.py` | `scripts/build_solution_proposal.py` | 生成旧本地模型方案文档的历史脚本 |

## 历史配置

- ASR：`faster-whisper/small.en`，旧环境也运行过 `openai-whisper/tiny.en`。
- 说话人分离：`pyannote/speaker-diarization-community-1`。
- 并发：单 Worker、并发 1。
- 设备：自动选择 CUDA，失败时回退 CPU。
- 依赖基线：PyTorch/Torchaudio 2.8、TorchCodec 0.7、faster-whisper 1.2.1、pyannote.audio 4.0.7。
- 历史精度继续记录在 `evaluation/baselines.json`，不代表当前生产模型。

## 恢复方式

1. 新建独立分支，不要直接修改生产部署。
2. 将 `backend/` 中四个模型模块复制回 `backend/app/`，并将 `local_provider.py` 接入 Provider层。
3. 根据服务器 CUDA、驱动和显存重新选择 PyTorch依赖；不要直接把历史 CPU镜像当作 GPU生产镜像。
4. 接受 Community-1模型条款并通过服务器 Secret配置 `HF_TOKEN`。
5. 恢复独立的 `local-speech` 队列和单并发 Worker。
6. 重新运行 Map Task和AMI评测后，才能决定是否进入生产。

## 隔离约束

- 活跃代码不得导入本目录。
- 本目录被生产 Docker构建上下文排除。
- 默认测试发现、Compose启动和发布包均不得包含本地模型运行依赖。
- 源码交付包保留本目录作为历史资料。
