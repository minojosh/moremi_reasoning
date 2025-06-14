# openai_client.py
# Wrapper around OpenAI API interactions
import os
from openai import OpenAI

class OpenAIClient:
    """
    Simplified OpenAI client for sending prompts and receiving responses.
    """
    def __init__(self, api_url: str, model_name: str):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client = OpenAI(api_key=api_key, api_base=api_url)
        self.model = model_name

    def send(self, prompt: str, image_urls: list = None, **kwargs) -> str:
        """
        Send a chat completion request using the configured model and prompt.
        """
        messages = [{"role": "user", "content": prompt}]
        # Note: image_urls handling can be added if model supports multimodal input.
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from OpenAI API")
        return content

    def send_text_only(self, prompt: str, **kwargs) -> str:
        """
        Use a text-only model for verification tasks.
        """
        return self.send(prompt, **kwargs)
