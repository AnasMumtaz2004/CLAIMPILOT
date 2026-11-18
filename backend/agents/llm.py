
import os
from dotenv import load_dotenv

load_dotenv(override=True)


def get_llm(provider, model_name, temperature, timeout_seconds, max_retries):
    """Create the chat model for an agent."""

    if provider == "groq":
        from langchain_groq import ChatGroq

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError("GROQ_API_KEY is missing from environment")

        return ChatGroq(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = os.getenv("GOOGLE_API_KEY")

        if not api_key:
            raise ValueError("GOOGLE_API_KEY is missing from environment")

        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    raise ValueError(f"Unknown model provider: {provider}")
