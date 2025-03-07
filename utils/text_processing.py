from langchain_text_splitters import RecursiveCharacterTextSplitter
import re
import os
from sentence_transformers import SentenceTransformer
class TextProcessor:

    _EMBEDDING_NAME = "sentence-transformers/all-MiniLM-L12-v2"
    def __init__(self):
        """
        文本处理工具类
        :param model_max_length: 模型最大序列长度，默认512
        """
        self._init_embedding_model()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.model.max_seq_length,
            chunk_overlap=int(self.model.max_seq_length * 0.1),
            length_function=lambda x: len(self.model.tokenizer.tokenize(x)),
            separators=['\n\n```', '\n\n', '\n', ' ', '']

        )
        
    def _init_embedding_model(self):
        """加载文本嵌入模型"""
        try:
            self.model = SentenceTransformer(self._EMBEDDING_NAME, local_files_only=True)
        except Exception as e:
            print(f"本地模型加载失败: {e}, 尝试在线下载...")
            self.model = SentenceTransformer(self._EMBEDDING_NAME)

        print(f"[Model] 嵌入维度: {self.model.get_sentence_embedding_dimension()}")
        print(f"[Model] 最大序列长度: {self.model.max_seq_length}")
        
    def clean_code(self, code: str, file_extension: str=None) -> str:
        """代码清洗标准化方法"""
        # 语言特定规则
        if file_extension == '.py':
            code = re.sub(r'#.*', '', code)
            code = re.sub(r'\'\'\'(.*?)\'\'\'', '', code, flags=re.DOTALL)
            code = re.sub(r'\"\"\"(.*?)\"\"\"', '', code, flags=re.DOTALL)
        elif file_extension in ('.cpp', '.ts', '.js'):
            code = re.sub(r'//.*', '', code)
            code = re.sub(r'/\*(.*?)\*/', '', code, flags=re.DOTALL)
        
        # 通用处理规则
        code = re.sub(r'\n{3,}', '\n\n', code)  # 压缩多空行
        code = re.sub(r'(?<=\n)\s+', ' ', code)  # 保留缩进空格
        return code.strip()

    def chunk_text(self, text: str,file_extension: str=None):
        """
        文本分块处理
        :return: (文本块列表, 嵌入向量列表)
        """
        chunks = self.text_splitter.split_text(self.clean_code(text,file_extension))
        
        return chunks, [self.model.encode(chunk) for chunk in chunks]
    
    
    def process_directory(self, directory: str) -> tuple:
        """处理目录中的代码文件"""
        filenames, texts, embeddings = [], [], []
        
        for root, _, files in os.walk(directory):
            for file in files:
                if not file.endswith('.py'):
                    continue
                
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                chunks, chunk_embeddings = self.chunk_text(content, '.py')
                
                filenames.extend([file_path] * len(chunks))
                texts.extend(chunks)
                embeddings.extend(chunk_embeddings)
        
        return filenames, texts, embeddings