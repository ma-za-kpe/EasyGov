import logging
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

logger = logging.getLogger(__name__)

class ExplanationGenerator:
    """
    Generates simplified, actionable explanations for various government documents using OpenAI's API.
    """
    
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not self.openai_api_key:
            logger.error("OPENAI_API_KEY not set, explanations will use fallback")
        self.llm = None
        if self.openai_api_key:
            try:
                self.llm = ChatOpenAI(
                    temperature=0.7,
                    model_name="gpt-3.5-turbo",
                    openai_api_key=self.openai_api_key
                )
                logger.info("Initialized OpenAI LLM for explanation generation")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI LLM: {str(e)}")
    
    def generate_explanation(self, summary_text, region_name=""):
        """
        Generate a simplified, actionable explanation in English focused on how a government
        document impacts women, explaining specific laws, policies, and actions.
        """
        if not summary_text or len(summary_text.strip()) < 10 or len(summary_text) > 1000:
            logger.warning(f"Invalid summary text for explanation: length={len(summary_text)}")
            return self._get_fallback_explanation(region_name)
            
        try:
            logger.debug(f"Original summary: {summary_text}")
            summary_text = summary_text.strip().replace('\n', ' ').replace('\r', '')
            if len(summary_text) > 500:
                summary_text = summary_text[:500] + "..."
            logger.debug(f"Cleaned summary_text: {summary_text}")
                
            region_context = f" in {region_name}" if region_name else ""
            
            prompt_template = PromptTemplate.from_template(
                """
                You are an experienced female community leader who has worked in women’s development for many years. You're known for explaining all kinds of government documents in clear, relatable terms to women of all backgrounds, helping them understand what’s happening and what they can do.

                Please create a warm, conversational message (100-150 words) explaining a government document{region_context}: "{summary_text}"

                Your message should:
                - Sound like friendly advice from a caring, knowledgeable woman working in women’s development
                - Use a warm, encouraging tone without lists or technical jargon
                - Explain what the document is about, using details from the summary, and why it matters to women’s lives (e.g., better education, healthcare, jobs)
                - Clarify any laws, policies, or terms mentioned in the summary (e.g., specific laws, programs, or initiatives) in simple language
                - Describe what the government is doing (e.g., starting programs, allocating funds) based on the summary
                - Say when women might see changes (e.g., soon, this year)
                - Suggest 2-3 specific actions women can take to benefit from or engage with the document’s initiatives (e.g., contact a specific office, join a group, attend a meeting)
                - Recommend where to get more information (e.g., relevant ministry, local government office)

                Use short sentences and simple words for all literacy levels. Focus on practical steps and positive impacts, ensuring actions and explanations are directly tied to the document’s content.
                """
            )
            
            if self.llm:
                try:
                    chain = prompt_template | self.llm
                    explanation = chain.invoke({
                        "summary_text": summary_text,
                        "region_context": region_context
                    }).content.strip()
                    if explanation and len(explanation) > 50:
                        logger.info(f"Generated explanation: {explanation[:100]}...")
                        return explanation
                    logger.warning("Generated explanation too short or invalid")
                except Exception as e:
                    logger.error(f"Error generating explanation with OpenAI: {str(e)}")
            
            logger.warning("OpenAI LLM unavailable or failed, using fallback explanation")
            return self._get_fallback_explanation(region_name)
            
        except Exception as e:
            logger.error(f"Error generating explanation: {str(e)}")
            return self._get_fallback_explanation(region_name)
    
    def _get_fallback_explanation(self, region_name=""):
        """Return a fallback explanation when model generation fails"""
        region_text = f" in {region_name}" if region_name else ""
        return (
            f"This government document{region_text} may help women and girls with opportunities like education, healthcare, or jobs. "
            f"It focuses on fairness and supporting women. To learn more, visit your local government office or community center. "
            f"You can ask about new programs, join a women’s group, or attend local meetings to get involved."
        )