import logging
import os
import requests
import time

logger = logging.getLogger(__name__)
 
 
class ExplanationGenerator:
    """
    Generates simplified explanations for government documents using the Hugging Face Inference API.
    """
    
    def __init__(self):
        # Use a model suited for text generation/explanation
        self.model_name = os.getenv("LLM_MODEL", "mistralai/Mixtral-8x7B-Instruct-v0.1")
        self.hf_token = os.getenv("HF_TOKEN", "")  # Hugging Face token
        
    def generate_explanation(self, summary_text, region_name=""):
        """
        Generate a simplified explanation in English focused on how the government document
        impacts gender equality (SDG 5) and reduced inequalities (SDG 10).
        """
        # Check if text is empty, too short, or malformed
        if not summary_text or len(summary_text.strip()) < 10 or len(summary_text) > 1000:
            logger.warning(f"Invalid summary text for explanation: length={len(summary_text)}")
            return self._get_fallback_explanation(region_name)
            
        try:
            # Clean summary text to prevent truncation or formatting issues
            summary_text = summary_text.strip().replace('\n', ' ').replace('\r', '')
            if len(summary_text) > 500:  # Truncate to avoid API limits
                summary_text = summary_text[:500] + "..."
                
            # Create a prompt that works for any region
            region_context = f" in {region_name}" if region_name else ""
            
            prompt = (
                f"You are an expert at explaining complex government documents in very simple language. "
                f"Below is a summary of a government document{region_context}: \"{summary_text}\"\n\n"
                f"In 100-150 words, explain clearly and simply how this document affects:\n"
                f"1. Gender equality (e.g., women, girls, gender minorities)\n"
                f"2. Reducing inequalities (e.g., poor communities, disabled people, rural areas)\n"
                f"Use short sentences. Avoid technical words. Mention specific positive and negative impacts. "
                f"Write for someone who reads at a basic level. Do not repeat the summary or this prompt."
            )
            
            # Use Hugging Face Inference API if token is available
            if self.hf_token:
                return self._generate_with_hf_api(prompt)
                
            logger.warning("No Hugging Face token available, using fallback explanation")
            return self._get_fallback_explanation(region_name)
            
        except Exception as e:
            logger.error(f"Error generating explanation: {str(e)}")
            return self._get_fallback_explanation(region_name)
    
    def _generate_with_hf_api(self, prompt):
        """Generate explanation using Hugging Face Inference API with retries"""
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                api_url = f"https://api-inference.huggingface.co/models/{self.model_name}"
                headers = {"Authorization": f"Bearer {self.hf_token}"}
                
                payload = {
                    "inputs": prompt,
                    "parameters": {
                        "max_length": 250,  # Reduced to align with shorter explanation
                        "min_length": 80,
                        "do_sample": False,
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "return_full_text": False  # Avoid returning prompt
                    }
                }
                
                response = requests.post(api_url, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Robust response handling
                    if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
                        if "generated_text" in result[0]:
                            explanation = result[0]["generated_text"].strip()
                            if explanation and len(explanation) > 50:
                                return explanation
                        elif "summary_text" in result[0]:
                            explanation = result[0]["summary_text"].strip()
                            if explanation and len(explanation) > 50:
                                return explanation
                    elif isinstance(result, dict) and "generated_text" in result:
                        explanation = result["generated_text"].strip()
                        if explanation and len(explanation) > 50:
                            return explanation
                            
                    logger.warning(f"Invalid or empty API response: {result}")
                
                logger.warning(f"HF API error on attempt {attempt+1}: {response.status_code} - {response.text}")
                
            except Exception as e:
                logger.error(f"Error with HF API on attempt {attempt+1}: {str(e)}")
                
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                
        logger.error(f"All {max_retries} attempts to generate explanation with HF API failed")
        return self._get_fallback_explanation()
        
    def _get_fallback_explanation(self, region_name=""):
        """Return a fallback explanation when model generation fails"""
        region_text = f" in {region_name}" if region_name else ""
        return (
            f"This government document{region_text} may support gender equality and reduce inequalities. "
            f"It could help women and girls with better access to education, healthcare, or jobs. "
            f"For marginalized groups, like people in rural areas or with disabilities, it might improve services or rights. "
            f"But the impact depends on how the document is used and if it reaches those who need it most."
        )