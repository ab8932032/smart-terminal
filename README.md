# smart-terminal
Try to access the local knowledge base through python code while calling the platform's instructions to directly operate the general solution of pc or other terminals

以下是适合放入README.md的文件结构注释说明：

```markdown
## 项目文件结构说明
smart-terminal/
├── configs/                   # 配置文件目录
│   ├── model_config.yaml      # 模型接入配置（适配器路径、端点地址等）
│   ├── db_config.yaml         # 数据库连接配置
│   └── process_config.yaml    # 问答流程控制配置
│
├── adapters/                  # 适配器层实现
│   ├── model/                 # 大模型适配器
│   │   ├── ollama_adapter.py  # Ollama API适配器
│   │   └── hf_pipeline.py     # HuggingFace Pipeline适配器
│   ├── vectordb/              # 向量数据库适配器
│   │   └── milvus_adapter.py  # Milvus数据库操作实现
│   └── frontends/             # 前端界面适配
│	  ├── event_bindings.py      # 事件绑定处理
│       ├── tkinter_gui.py     # Tkinter桌面端实现
│       └── web_api.py         # Web API接口实现
│
├── core/                      # 核心业务逻辑
│   ├── retrieval_service.py   # 混合检索服务（稠密+稀疏检索）
│   ├── qa_engine.py           # 问答引擎（多轮对话处理）
│   ├── process_controller.py  # 流程控制器（多阶段问答控制）
│   ├── events.py              # 事件类型定义（配合event_bus使用）
│   └── event_bus.py           # 事件总线（模块间通信）
│
│
├── services/                  # 辅助服务组件
│   ├── command_processor.py   # 命令行解析与执行
│   ├── safety_checker.py      # 危险命令检测
│   └── session_manager.py     # 对话会话管理
│
├── utils/                     # 通用工具类
│   ├── text_processing.py     # 文本清洗/分块处理
│   ├── template_manager.py    # Jinja2模板引擎封装，管理templates目录下的jinja文件
│   ├── config_loader.py       # yaml配置文件加载
│   └── logger.py              # 日志系统配置
│
├── templates/                 # 提示词模板
│   ├── thought_gen.jinja      # 思考过程生成模板
│   ├── interim_answer.jinja   # 中间答案生成模板
│   ├── system_prompt.jinja    # 系统提示词主模板 
│   ├── knowledge_rules.jinja  # 知识库规则 
│   ├── response_format.jinja  # 响应格式 
│   └── special_cases.jinja    # 特殊场景
│
├── tests/                     # 单元测试
│   ├── test_adapters/         # 适配器测试用例
│   └── test_services/         # 服务组件测试用例
│
└── entrypoints/               # 程序入口
    ├── cli_app.py             # 命令行入口
    └── gui_app.py             # GUI应用入口
```

### 关键文件说明

1. **configs/model_config.yaml**  
   模型服务配置示例：
   ```yaml
   model_providers:
     ollama:
       adapter: adapters.model.ollama_adapter.OllamaAdapter
       endpoint: "http://localhost:11434"
       models:
         default: "deepseek-r1:7b"
   ```

2. **core/process_controller.py**  
   多阶段问答流程控制核心类，实现以下处理逻辑：
   ```python
   async def execute_flow(self, question: str) -> dict:
       # 1. 初始问题分析
       # 2. 知识库检索判断
       # 3. 多轮结果综合
       # 4. 最终答案生成
   ```

3. **adapters/frontends/tkinter_gui.py**  
   GUI前端主要实现：
   ```python
   class TkinterFrontend:
       def __init__(self):
           # 构建界面元素
           self._build_input_panel()  # 输入面板
           self._build_display_area() # 展示区域
           self._bind_events()        # 事件绑定
   ```

# 启动GUI应用
```bash
cd smart-terminal
python -m entrypoints.gui_app
```

# 该结构支持以下扩展方式：
1. **新增模型适配器**：在`adapters/model/`添加实现类，并更新配置文件
2. **更换前端界面**：实现新的Frontend子类并修改入口配置
3. **自定义流程**：继承`ProcessController`并重写执行逻辑
```