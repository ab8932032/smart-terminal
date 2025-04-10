from typing import Dict, List

import torch
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredMarkdownLoader, CSVLoader,BSHTMLLoader
from pathlib import Path
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
from summa import summarizer

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
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.embeddings._client.max_seq_length*0.8,  # 保留20%余量应对tokenization长度波动 
            chunk_overlap=int(0.1 * self.embeddings._client.max_seq_length), #推荐10%的重叠比例
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
                encode_kwargs=encode_kwargs,
                multi_process=False  # 可选性能优化
            )
        except Exception:
            # 如果失败，使用默认参数初始化嵌入模型
            self.embeddings = HuggingFaceEmbeddings(model_name=self._EMBEDDING_NAME,multi_process=True)

        # 打印模型信息
        print(f"[Model] 嵌入维度: {self.embeddings._client.get_sentence_embedding_dimension()}")
        print(f"[Model] 最大序列长度: {self.embeddings._client.max_seq_length}")

    def _load_file_content(self, file_path: Path) -> list[Document]:
            ext = file_path.suffix.lower()
            loaderClass = self._SUPPORTED_EXTENSIONS.get(ext)
            
            if not loaderClass:
                raise ValueError(f"Unsupported file type: {ext}")

            try:
                loader = loaderClass(str(file_path))
                docs = loader.load()
                return docs
            except Exception as e:
                print(f"文件加载失败: {file_path} -> {str(e)}")
                return []
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
            text_chunks = [
                chunk.page_content
                for chunk in chunks
                if chunk.page_content.strip()
            ]
            # 生成嵌入
            if not text_chunks:
                continue  # 跳过空内容
                
            chunk_embeddings = self.embeddings.embed_documents(text_chunks)
            # 收集结果
            filenames.extend([str(file_path)] * len(text_chunks))
            texts.extend(text_chunks)
            embeddings.extend(chunk_embeddings)
        
        return filenames, texts, embeddings

    def extract_key_info(self, text: str, reference_texts: list = None) -> Dict[str, any]:
        """
        独立的关键信息提取（不依赖 process_directory）
        参数:
            reference_texts: 用于对比的参考文本列表（可选）
        """
        # 获取当前文本的嵌入
        text_embedding = self.embeddings.embed_query(text)
    
        # 使用正则表达式提取名词短语（替代spacy）
        import re
        from collections import Counter
        # 提取连续的2-4个单词组合作为候选短语
        phrases = re.findall(r'\b(?:\w+\s+){1,3}\w+\b', text.lower())
        # 过滤掉常见停用词
        stopwords = {
            # 英文停用词
            'a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'was', 'were', 
            'be', 'been', 'to', 'of', 'in', 'on', 'at', 'for', 'with', 'as', 'by',
            # 中文停用词
            '的', '了', '和', '是', '在', '有', '我', '你', '他', '她', '它', 
            '我们', '你们', '他们', '这个', '那个', '这些', '那些', '可以', '可能',
            '会', '要', '也', '都', '就', '不', '没有', '很', '非常', '什么',
            '怎么', '为什么', '如何', '因为', '所以', '但是', '而且', '然后'
        }
        key_phrases = [
            phrase for phrase in phrases 
            if not all(word in stopwords for word in phrase.split())
        ]
        # 取频率最高的5个短语
        key_phrases = [phrase for phrase, _ in Counter(key_phrases).most_common(5)]
    
        # 相似度计算逻辑
        avg_similarity = 0.0
        if reference_texts:
            # 动态生成参考文本的嵌入
            ref_embeddings = self.embeddings.embed_documents(reference_texts)
    
            # 使用 PyTorch 直接计算相似度
            text_tensor = torch.tensor(text_embedding).unsqueeze(0)
            ref_tensors = torch.tensor(ref_embeddings)
            similarities = torch.nn.functional.cosine_similarity(
                text_tensor, ref_tensors
            )
            avg_similarity = similarities.mean().item()
    
        return {
            "key_phrases": key_phrases,
            "similarity": avg_similarity
        }

    def summarize_text(self, text: str, ratio=0.6) -> str:
        """基于TextRank的摘要提取"""
        result = summarizer.summarize(text, ratio=ratio, language='chinese')
        return result
    
    def semantic_compress(self, text: str, threshold=0.8) -> str:
        """基于语义相似度的压缩"""
        sentences = text.split('.')
        if len(sentences) <= 1:
            return text
            
        embeddings = self.embeddings.embed_documents(sentences)
        compressed = [sentences[0]]
        
        for i in range(1, len(sentences)):
            sim = torch.nn.functional.cosine_similarity(
                torch.tensor(embeddings[i-1]).unsqueeze(0),
                torch.tensor(embeddings[i]).unsqueeze(0)
            )
            if sim < threshold:
                compressed.append(sentences[i])
                
        return '.'.join(compressed)
    
    def truncate_history(self, history: List[Dict], max_tokens=512) -> List[Dict]:
        """截断策略"""
        current_length = sum(len(msg["content"]) for msg in history)
        while current_length > max_tokens and len(history) > 1:
            history.pop(0)  # 移除最早的消息
            current_length = sum(len(msg["content"]) for msg in history)
        return history