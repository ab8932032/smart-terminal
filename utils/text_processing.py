import torch
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.document_loaders import PyPDFLoader, TextLoader, UnstructuredMarkdownLoader, CSVLoader,BSHTMLLoader
from pathlib import Path
import re
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

class TextProcessor:
    _EMBEDDING_NAME = "sentence-transformers/all-MiniLM-L12-v2"
    _SUPPORTED_EXTENSIONS = {
            ".pdf": PyPDFLoader,
            ".txt": TextLoader,
            ".md": UnstructuredMarkdownLoader,
            ".csv": CSVLoader,
            ".py": TextLoader,  # 保留原有Python处理
            ".cpp": TextLoader,
            ".h": TextLoader,
            ".js": TextLoader,
            ".ts": TextLoader,
            ".html": BSHTMLLoader
        }
    def __init__(self):
        # 初始化嵌入模型
        self._init_embeddings()
        # 初始化文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter.from_huggingface(
            model_name=self._EMBEDDING_NAME,
            chunk_size=self.embeddings.model.max_seq_length,
            chunk_overlap=int(0.1 * self.embeddings.model.max_seq_length),
            separators=["\n\n```", "\n\n", "\n", " ", ""]
        )

    def _init_embeddings(self):
        # 设置模型运行设备和嵌入参数
        model_kwargs = {"device": "cuda" if torch.cuda.is_available() else "cpu"}
        encode_kwargs = {"normalize_embeddings": True}

        try:
            # 尝试初始化嵌入模型
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self._EMBEDDING_NAME,
                model_kwargs=model_kwargs,
                encode_kwargs=encode_kwargs
            )
        except Exception:
            # 如果失败，使用默认参数初始化嵌入模型
            self.embeddings = HuggingFaceEmbeddings(model_name=self._EMBEDDING_NAME)

        # 打印模型信息
        print(f"[Model] 嵌入维度: {self.embeddings.query_dimension}")
        print(f"[Model] 最大序列长度: {self.embeddings.model_max_length}")

    def chunk_text(self, docs) -> tuple:
        # 分割文本为块
        chunks = self.text_splitter.split_documents(docs)
        # 为每个块生成嵌入
        embeddings = self.embeddings.embed_documents(chunks)
        
        # 过滤掉空块
        valid = [(c, e) for c, e in zip(chunks, embeddings) if c.strip()]
        return list(zip(*valid)) if valid else ([], [])

    def _load_file_content(self, file_path: Path) -> str:
            ext = file_path.suffix.lower()
            LoaderClass = self._SUPPORTED_EXTENSIONS.get(ext)
            
            if not LoaderClass:
                raise ValueError(f"Unsupported file type: {ext}")

            try:
                loader = LoaderClass(str(file_path))
                docs = loader.load()
                return docs
            except Exception as e:
                print(f"文件加载失败: {file_path} -> {str(e)}")
                return None
    def _load_ignore_spec(self, root_dir: str, ignore_file: str = ".textignore") -> PathSpec:
        """加载忽略规则，默认使用项目根目录的.ignore文件"""
        root_path = Path(root_dir)
        ignore_path = root_path / ignore_file
        
        # 允许使用.gitignore或自定义文件
        if not ignore_path.exists():
            ignore_path = root_path / ".gitignore"
        
        try:
            with open(ignore_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        except FileNotFoundError:
            lines = []
        
        return PathSpec.from_lines(GitWildMatchPattern, lines)

    def process_directory(self, directory: str) -> tuple:
        root_path = Path(directory)
        ignore_spec = self._load_ignore_spec(directory)
        filenames, texts, embeddings = [], [], []

        for file_path in root_path.rglob("*"):
            if not file_path.is_file():
                continue

            rel_path = str(file_path.relative_to(root_path))
            if ignore_spec.match_file(rel_path):
                continue

            ext = file_path.suffix.lower()
            if ext not in self._SUPPORTED_EXTENSIONS:
                continue  # 跳过不支持的文件类型

            try:
                docs = self._load_file_content(file_path)
                if not docs:
                    continue  # 跳过空文件
            except UnicodeDecodeError:
                continue  # 跳过编码错误文件

            # 分割文档并提取纯文本内容
            chunks = self.text_splitter.split_documents(docs)
            text_chunks = [doc.page_content for doc in chunks]  # 提取纯文本
            
            # 生成嵌入
            if not text_chunks:
                continue  # 跳过空内容
            chunk_embeddings = self.embeddings.embed_documents(text_chunks)
            
            # 收集结果
            filenames.extend([str(file_path)] * len(text_chunks))
            texts.extend(text_chunks)
            embeddings.extend(chunk_embeddings)
        
        return filenames, texts, embeddings