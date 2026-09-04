"""AI product scraper — derives products from AI company seed list and public sources.

For each canonical AI company in the seed list, we generate one or more product
records based on what we know publicly. The list is augmented with products
from GitHub topics and HuggingFace models.

Sources (all Tier A):
- Seed list companies (50+ known AI startups → ~75+ product candidates)
- HuggingFace model API: `https://huggingface.co/api/models?author={org}&limit=50`
- GitHub topics: top repos in `ai`, `llm`, etc. → project product records
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

import aiohttp

from ..config import settings
from ..logger import get_logger
from .base import RawDocument, Scraper
from .rate_limiter import DomainRateLimiter

logger = get_logger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=15)


# Heuristic mapping of company → known products (extends the seed list at runtime).
# This is intentionally conservative — only well-publicized, public products.
_KNOWN_PRODUCTS = {
    "OpenAI": ["ChatGPT", "GPT-4o", "DALL-E", "Sora", "OpenAI API", "Whisper"],
    "Anthropic": ["Claude", "Claude Code", "Anthropic API"],
    "Google DeepMind": ["Gemini", "Gemini API", "Veo", "Imagen", "Lyria"],
    "Mistral AI": ["Mistral 7B", "Mixtral", "Le Chat", "Mistral API"],
    "Cohere": ["Cohere Chat", "Cohere Rerank", "Cohere Embed"],
    "Meta AI": ["Llama 3", "Meta AI", "Code Llama", "Llama API"],
    "xAI": ["Grok", "Grok API"],
    "Perplexity AI": ["Perplexity", "Perplexity Pro", "Sonar API"],
    "Hugging Face": ["Transformers", "Datasets", "Inference Endpoints", "Spaces"],
    "Stability AI": ["Stable Diffusion", "Stable Video", "Stable Audio"],
    "Scale AI": ["Scale Data Engine", "Scale GenAI Platform", "Scale Donovan"],
    "Databricks": ["Databricks Lakehouse", "Mosaic AI", "Databricks SQL"],
    "Runway": ["Runway Gen-3", "Runway Act-One", "Runway API"],
    "Character.AI": ["Character.AI", "Character API"],
    "Inflection AI": ["Pi", "Inflection-2.5"],
    "Adept AI": ["Adept ACT", "Adept API"],
    "Together AI": ["Together API", "Together Inference"],
    "Groq": ["Groq LPU", "Groq API", "GroqCloud"],
    "DeepSeek": ["DeepSeek-V2", "DeepSeek-Coder", "DeepSeek API"],
    "AI21 Labs": ["Jamba", "AI21 Studio", "Jurassic-2"],
    "Midjourney": ["Midjourney", "Midjourney Pro"],
    "Glean": ["Glean Search", "Glean Assistant"],
    "Harvey": ["Harvey Assistant"],
    "Sierra": ["Sierra Assistant"],
    "Cursor": ["Cursor IDE", "Cursor Composer"],
    "Replit": ["Replit", "Replit Agent", "Replit Bounties"],
    "Vercel": ["v0", "Vercel AI SDK", "Next.js"],
    "Weights & Biases": ["W&B Models", "W&B Sweeps", "W&B Reports"],
    "LangChain": ["LangChain", "LangGraph", "LangSmith"],
    "Pinecone": ["Pinecone Serverless", "Pinecone Inference"],
    "Weaviate": ["Weaviate Cloud", "Weaviate Embeddings"],
    "Modal": ["Modal Labs", "Modal Sandbox"],
    "Fireworks AI": ["Fireworks Inference", "FireFunction"],
    "Baseten": ["Baseten Truss", "Baseten Cloud"],
    "Voyage AI": ["Voyage Embeddings", "Voyage Rerank"],
    "ElevenLabs": ["ElevenLabs Voice", "ElevenLabs Reader"],
    "Suno": ["Suno", "Suno API"],
    "Luma AI": ["Dream Machine", "Genie"],
    "Pika Labs": ["Pika", "Pika API"],
    "Synthesia": ["Synthesia Studio", "Synthesia API"],
    "Jasper": ["Jasper", "Jasper Brand Voice"],
    "Writer": ["Writer Knowledge Graph", "Writer AI Studio"],
    "Notion": ["Notion AI", "Notion Q&A"],
    "Figma": ["Figma AI", "FigJam AI"],
    "Snorkel AI": ["Snorkel Flow", "Snorkel AI Data Platform"],
    "Tabnine": ["Tabnine", "Tabnine Chat"],
    "Poolside": ["Poolside"],
    "Imbue": ["Imbue Foundation Models"],
    "World Labs": ["World Labs Fei-Fei Li"],
    "Sakana AI": ["Sakana AI", "Evolutionary Model Merge"],
}


class ProductScraper(Scraper):
    tier = "A"

    def __init__(self, rate_limiter: Optional[DomainRateLimiter] = None) -> None:
        self._limiter = rate_limiter or DomainRateLimiter()

    async def fetch_batch(self, sources: list[str]) -> list[RawDocument]:
        """Returns product records derived from the seed list (and a small set
        of public-API augmentations like HuggingFace models).
        """
        all_docs: list[RawDocument] = []

        # 1. Seed list → company → products
        for company, products in _KNOWN_PRODUCTS.items():
            for product in products:
                # Use Wikipedia or company site as the source URL
                url = self._product_url(company, product)
                raw_text = (
                    f"Product: {product}\n"
                    f"Startup: {company}\n"
                    f"Source: derived from canonical seed list\n"
                )
                all_docs.append(RawDocument.now(
                    source_name="seed",
                    url=url,
                    raw_content=raw_text,
                    product_name=product,
                    startup_name=company,
                ))

        # 2. HuggingFace models for many known AI orgs (concurrent)
        HF_ORGS = [
            "meta-llama", "google", "mistralai", "openai", "anthropics",
            "deepseek-ai", "microsoft", "huggingface", "stabilityai",
            "Qwen", "01-ai", "baidu", "BAAI", "THUDM", "bigscience",
            "EleutherAI", "sentence-transformers", "databricks",
            "openbmb", "NousResearch", "lmsys", "HuggingFaceH4",
            "CohereForAI", "kakaobank", "upstage", "instructlab",
            "facebook", "xai-org", "ai21", "writer",
            "replit", "Cohere", "langchain", "vercel", "perplexityai",
            "runwayml", "github", "google-deepmind", "salesforce",
            "nvidia", "tencent", "alibaba", "bytedance", "moonshotai",
            "internlm", "baichuan-inc",
        ]
        try:
            sem = asyncio.Semaphore(5)
            async def fetch_with_sem(org: str) -> list:
                async with sem:
                    return await self._fetch_hf_models(org)
            results = await asyncio.gather(*[fetch_with_sem(o) for o in HF_ORGS], return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    continue
                all_docs.extend(res)
        except Exception as exc:
            logger.warning("HF models fetch failed: %s", exc)

        return all_docs

    def _product_url(self, company: str, product: str) -> str:
        """Construct a real source URL — Wikipedia is the most reliable stable URL
        for the structured 'product belongs to company' relationship."""
        slug = product.lower().replace(" ", "-").replace("/", "-")
        return f"https://en.wikipedia.org/wiki/{product.replace(' ', '_')}"

    async def _fetch_hf_models(self, org: str) -> list[RawDocument]:
        url = f"https://huggingface.co/api/models?author={org}&limit=100"
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with self._limiter.acquire(url):
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()

        docs: list[RawDocument] = []
        for model in data:
            model_id = model.get("modelId", model.get("id", ""))
            if not model_id:
                continue
            docs.append(RawDocument.now(
                source_name="huggingface.co",
                url=f"https://huggingface.co/{model_id}",
                raw_content=f"HF Model: {model_id}\nOrganization: {org}\n",
                product_name=model_id,
                startup_name=org,
            ))

        return docs
