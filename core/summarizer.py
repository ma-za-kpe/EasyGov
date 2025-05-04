# core/summarizer.py
import logging
import os
import requests
from typing import List, Dict, Any, Optional, Tuple

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Summarizer:
    """A document summarizer that uses LangChain and OpenAI."""
    
    def __init__(self):
        logger.info("Initializing Summarizer with LangChain and OpenAI")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.hf_api_key = os.getenv("HF_TOKEN", "")
        self.summary_type = "map_reduce"
        self.llm = None
        self.text_splitter = None
        self.summarizer_url = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
        
    def extract_text_from_pdf(self, pdf_path_or_url: str) -> str:
        logger.info(f"Extracting text from PDF: {pdf_path_or_url}")
        try:
            import pdfplumber
            import re
            
            # Handle both local file paths and URLs
            if os.path.isfile(pdf_path_or_url):
                logger.info(f"Using local PDF file at {pdf_path_or_url}")
                file_path = pdf_path_or_url
            else:
                logger.info(f"Downloading from URL: {pdf_path_or_url}")
                response = requests.get(pdf_path_or_url, timeout=120)
                response.raise_for_status()
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    temp_file.write(response.content)
                    file_path = temp_file.name
            
            text = ''
            max_pages = 10  # Limit to first 10 pages
            logger.info(f"Opening PDF from {file_path}")
            with pdfplumber.open(file_path) as pdf:
                logger.info(f"PDF has {len(pdf.pages)} pages")
                for i, page in enumerate(pdf.pages[:max_pages]):
                    page_text = page.extract_text()
                    if not page_text:
                        continue
                    
                    # Split page into lines and check for TOC characteristics
                    lines = page_text.split('\n')
                    if len(lines) > 20 and max(len(line.strip()) for line in lines) < 50:
                        logger.info(f"Skipping page {i+1} (likely TOC based on line count and length)")
                        continue
                    
                    # Filter out TOC-like lines (e.g., "2.0 ... 4", "Section Title ... 10")
                    filtered_lines = []
                    for line in lines:
                        line = line.strip()
                        # Skip lines that look like TOC entries
                        if re.match(r'^\d+\.\d+(\.\d+)?\s+.*\s+\.+\s+\d+$', line):  # e.g., "2.0 Title ... 4"
                            continue
                        if '...' in line and len(line) < 100:  # Short lines with ellipses
                            continue
                        if re.search(r'\s+\d+$', line) and len(line) < 100:  # Lines ending with page numbers
                            continue
                        filtered_lines.append(line)
                    
                    page_text = '\n'.join(filtered_lines)
                    if page_text:
                        text += page_text + '\n'
            
            if not os.path.isfile(pdf_path_or_url):
                os.unlink(file_path)
                logger.info(f"Deleted temp file: {file_path}")
            
            logger.info(f"Extracted {len(text)} characters from PDF")
            return text[:10000]  # Cap at 10,000 characters
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            return f"Error extracting text: {str(e)}"

    def _extract_sdg_relevant_text(self, text: str) -> str:
        logger.info(f"Extracting SDG-relevant text")
        keywords = [
            'gender', 'women', 'girls', 'female', 'maternal',
            'gender-based violence', 'gender equality', 'gender parity',
            'inequality', 'equity', 'disparity', 'marginalized', 'vulnerable',
            'inclusion', 'inclusive', 'discrimination', 'minority',
            'differently abled', 'disabilities', 'equal opportunity'
        ]
        
        import re
        relevant_paragraphs = []
        paragraphs = text.split('\n')
        logger.info(f"Analyzing {len(paragraphs)} paragraphs for SDG relevance")
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            # Skip short paragraphs (likely TOC entries or headings)
            if len(paragraph) < 50:
                continue
            # Skip paragraphs that look like TOC entries
            if re.match(r'^\d+\.\d+(\.\d+)?\s+.*$', paragraph):  # e.g., "2.0 Title"
                continue
            if '...' in paragraph or re.search(r'\s+\d+$', paragraph):  # Ellipses or page numbers
                continue
            # Check for SDG keywords
            if any(keyword.lower() in paragraph.lower() for keyword in keywords):
                relevant_paragraphs.append(paragraph)
        
        relevant_text = '\n'.join(relevant_paragraphs)
        
        if not relevant_text.strip():
            logger.warning("No SDG-relevant text found, using original text")
            return text[:4000]
        
        logger.info(f"Found {len(relevant_paragraphs)} SDG-relevant paragraphs ({len(relevant_text)} chars)")
        return relevant_text[:4000]

    def _create_langchain_docs(self, text: str) -> List[Any]:
        logger.info(f"Creating LangChain documents from {len(text)} chars of text")
        try:
            from langchain.docstore.document import Document
            from langchain_text_splitters import CharacterTextSplitter
            
            if not self.text_splitter:
                try:
                    self.text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
                        chunk_size=4000, 
                        chunk_overlap=200
                    )
                except ImportError:
                    self.text_splitter = CharacterTextSplitter(
                        chunk_size=4000,
                        chunk_overlap=200
                    )
            
            docs = [Document(page_content=text)]
            split_docs = self.text_splitter.split_documents(docs)
            logger.info(f"Split into {len(split_docs)} chunks")
            return split_docs
        except Exception as e:
            logger.error(f"Error creating LangChain documents: {str(e)}")
            return []

    def _create_map_reduce_chain(self) -> Any:
        try:
            from langchain.chains.combine_documents.stuff import StuffDocumentsChain
            from langchain.chains.mapreduce import MapReduceDocumentsChain, ReduceDocumentsChain
            from langchain.chains.llm import LLMChain
            from langchain_core.prompts import PromptTemplate
            
            map_template = """
            The following is a section of a document:
            {docs}
            
            Provide a concise summary of this section, focusing on key points related to gender equality, 
            social inclusion, and sustainable development:
            """
            map_prompt = PromptTemplate.from_template(map_template)
            map_chain = LLMChain(llm=self.llm, prompt=map_prompt)
            
            reduce_template = """
            The following are summaries of sections from a document:
            {docs}
            
            Take these summaries and create a final, cohesive summary that captures all key information
            about gender equality, social inclusion, and sustainable development goals.
            Focus on policies, impacts, and recommendations if present:
            """
            reduce_prompt = PromptTemplate.from_template(reduce_template)
            reduce_chain = LLMChain(llm=self.llm, prompt=reduce_prompt)
            
            combine_documents_chain = StuffDocumentsChain(
                llm_chain=reduce_chain, 
                document_variable_name="docs"
            )
            
            reduce_documents_chain = ReduceDocumentsChain(
                combine_documents_chain=combine_documents_chain,
                collapse_documents_chain=combine_documents_chain,
                token_max=4000,
            )
            
            map_reduce_chain = MapReduceDocumentsChain(
                llm_chain=map_chain,
                reduce_documents_chain=reduce_documents_chain,
                document_variable_name="docs",
                return_intermediate_steps=False,
            )
            
            return map_reduce_chain
        except Exception as e:
            logger.error(f"Error creating map-reduce chain: {str(e)}")
            return None
    
    def _fallback_to_huggingface(self, text: str) -> str:
        logger.info(f"Using HuggingFace API for summarization")
        try:
            if not self.hf_api_key:
                logger.warning("No Hugging Face token available")
                return "No Hugging Face API key provided for summarization."
                
            headers = {"Authorization": f"Bearer {self.hf_api_key}"}
            payload = {
                "inputs": text[:4000],
                "parameters": {
                    "max_length": 150,
                    "min_length": 50,
                    "do_sample": False
                }
            }
            response = requests.post(self.summarizer_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if isinstance(result, list) and len(result) > 0 and "summary_text" in result[0]:
                summary = result[0]["summary_text"]
                logger.info(f"Generated {len(summary)} character summary via HuggingFace")
                return summary
            else:
                logger.error(f"Unexpected response format from HuggingFace API: {result}")
                return "Error: Unexpected response format from summarization API"
        except Exception as e:
            logger.error(f"Error using HuggingFace API: {str(e)}")
            return f"Error generating summary: {str(e)}"
    
    def summarize_document(self, pdf_path_or_url: str) -> Tuple[str, str]:
        logger.info(f"Summarizing document from: {pdf_path_or_url}")
        try:
            text = self.extract_text_from_pdf(pdf_path_or_url)
            
            if text.startswith("Error extracting text"):
                logger.error(f"Failed to extract text: {text}")
                return text, None
            
            filtered_text = self._extract_sdg_relevant_text(text)
            
            if not filtered_text or len(filtered_text.strip()) < 50:
                logger.warning("Not enough text to summarize")
                return "Not enough relevant text found in document to generate a summary.", filtered_text
                
            llm_initialized = False
            if self.llm is None and self.openai_api_key:
                try:
                    from langchain_openai import ChatOpenAI
                    self.llm = ChatOpenAI(
                        temperature=0.3, 
                        model_name="gpt-3.5-turbo",
                        openai_api_key=self.openai_api_key
                    )
                    llm_initialized = True
                    logger.info("Initialized OpenAI LLM for summarization")
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI LLM: {str(e)}")
            
            summary = ""
            if self.llm is not None and llm_initialized:
                try:
                    logger.info(f"Using LangChain {self.summary_type} chain for summarization")
                    langchain_docs = self._create_langchain_docs(filtered_text)
                    if langchain_docs:
                        chain = self._create_map_reduce_chain()
                        if chain:
                            summary = chain.run(langchain_docs)
                            logger.info(f"Generated {len(summary)} character summary via LangChain")
                except Exception as e:
                    logger.error(f"Error using LangChain for summarization: {str(e)}")
                    summary = ""
            
            if not summary:
                logger.warning("LangChain summarization failed or not available. Falling back to HuggingFace API")
                summary = self._fallback_to_huggingface(filtered_text)
            
            if not summary or summary.startswith("Error") or summary.startswith("No Hugging Face"):
                logger.error("All summarization methods failed")
                summary = "Failed to generate summary due to API errors."
            
            return summary.strip(), filtered_text
            
        except Exception as e:
            logger.error(f"Error summarizing document: {str(e)}")
            return f"Error summarizing document: {str(e)}", None