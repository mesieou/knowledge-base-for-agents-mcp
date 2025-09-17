"""
OpenAI tokenizer wrapper for docling chunking
"""
import tiktoken
from typing import List


class OpenAITokenizerWrapper:
    """Tokenizer wrapper for OpenAI models compatible with docling HybridChunker"""

    def __init__(self, model: str = "text-embedding-3-large"):
        self.model = model
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")  # Use gpt-4 tokenizer as fallback

    def encode(self, text: str) -> List[int]:
        """Encode text to tokens"""
        return self.tokenizer.encode(text)

    def decode(self, tokens: List[int]) -> str:
        """Decode tokens back to text"""
        return self.tokenizer.decode(tokens)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.encode(text))
