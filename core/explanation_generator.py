# explanation_generator.py
import logging
import os
import requests
from transformers import pipeline
import time

logger = logging.getLogger(__name__)

class ExplanationGenerator:
    """
    Generates simplified explanations for budget documents using an open-source LLM,
    focused specifically on SDG 5 (Gender Equality) and SDG 10 (Reduced Inequalities).
    """
    
    def __init__(self):
        # Default to a smaller but effective model for summarization
        self.model_name = os.getenv("LLM_MODEL", "facebook/bart-large-cnn")
        self.hf_token = os.getenv("HF_TOKEN", "")  # Hugging Face token
        self.use_local_model = os.getenv("USE_LOCAL_MODEL", "True").lower() == "true"
        self.model = None
        
        if self.use_local_model:
            try:
                logger.info(f"Loading local model: {self.model_name}")
                # Fix for deprecated parameter warning
                self.model = pipeline("summarization", model=self.model_name, token=self.hf_token)
                logger.info("Model loaded successfully")
            except Exception as e:
                logger.error(f"Error loading local model: {str(e)}")
                self.model = None
    
    def generate_explanation(self, summary_text, region_name=""):
        """
        Generate a simplified explanation in English focused on how the budget impacts
        gender equality (SDG 5) and reduced inequalities (SDG 10).
        
        Args:
            summary_text: The budget text to explain
            region_name: Optional name of the region (e.g., "Uganda", "Ghana")
            
        Returns:
            A simplified explanation text in English
        """
        # Check if text is empty or too short
        if not summary_text or len(summary_text.strip()) < 10:
            logger.warning("Summary text is empty or too short for explanation generation")
            return self._get_fallback_explanation(region_name)
            
        try:
            # Create a prompt that works for any region
            region_context = f" in {region_name}" if region_name else ""
            
            prompt = (
                f"The following is a budget excerpt{region_context}: \"{summary_text}\"\n\n"
                f"Explain in simple, accessible language how this budget affects:\n"
                f"1. Gender equality (women, girls, and gender minorities)\n"
                f"2. Reduction of inequalities (marginalized and vulnerable populations)\n"
                f"Be specific about both positive and negative impacts. Explain as if speaking to "
                f"someone with limited literacy or technical knowledge."
            )
            
            # Use local model if available
            if self.model and self.use_local_model:
                return self._generate_with_local_model(prompt)
            
            # Otherwise use Hugging Face Inference API if token is available
            elif self.hf_token:
                return self._generate_with_hf_api(prompt)
                
            # If no generation method is available, return a fallback explanation
            logger.warning("No LLM generation method available, using fallback explanation")
            return self._get_fallback_explanation(region_name)
            
        except Exception as e:
            logger.error(f"Error generating explanation: {str(e)}")
            return self._get_fallback_explanation(region_name)
    
    def _generate_with_local_model(self, prompt):
        """Generate explanation using local model with retries"""
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                result = self.model(prompt, max_length=200, min_length=80, do_sample=False)
                
                if result and isinstance(result, list) and len(result) > 0:
                    explanation = result[0]['summary_text']
                    
                    # Validate the output is substantial enough
                    if len(explanation.strip()) < 20:
                        logger.warning(f"Generated explanation too short: {explanation}")
                        continue  # Try again
                        
                    return explanation
                else:
                    logger.warning(f"Model returned empty or invalid result on attempt {attempt+1}")
                    
            except Exception as e:
                logger.error(f"Error with local model on attempt {attempt+1}: {str(e)}")
                
            # Wait before retrying
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                
        # If all attempts failed, return a fallback explanation
        logger.error(f"All {max_retries} attempts to generate explanation failed")
        return "This budget likely has implications for gender equality and reducing inequalities. It may affect funding for programs that support women, girls, and marginalized communities."
    
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
                        "max_length": 200,
                        "min_length": 80,
                        "do_sample": False
                    }
                }
                
                response = requests.post(api_url, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Handle different response formats based on model type
                    if isinstance(result, list) and len(result) > 0:
                        if isinstance(result[0], dict) and "summary_text" in result[0]:
                            return result[0]["summary_text"]
                        elif isinstance(result[0], dict) and "generated_text" in result[0]:
                            return result[0]["generated_text"]
                        else:
                            return result[0]
                
                logger.warning(f"HF API error on attempt {attempt+1}: {response.status_code} - {response.text}")
                
            except Exception as e:
                logger.error(f"Error with HF API on attempt {attempt+1}: {str(e)}")
                
            # Wait before retrying
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                
        # If all attempts failed, return a fallback explanation
        logger.error(f"All {max_retries} attempts to generate explanation with HF API failed")
        return "This budget likely has implications for gender equality and reducing inequalities. It may affect funding for programs that support women, girls, and marginalized communities."
        
    def _get_fallback_explanation(self, region_name=""):
        """Return a fallback explanation when model generation fails"""
        region_text = f" in {region_name}" if region_name else ""
        
        # Create a generic but helpful explanation that focuses on SDG 5 and SDG 10
        return (
            f"This budget{region_text} contains provisions that may impact gender equality and reduce inequalities. "
            f"For women and girls, it could affect access to education, healthcare, and economic opportunities. "
            f"For marginalized communities, it might influence social services, infrastructure development, and protection programs. "
            f"The specific impacts depend on funding allocations and implementation."
        )