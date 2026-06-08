import json
import logging
import re
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ChatSummary(BaseModel):
    parties: list[str]
    dispute_amount: Optional[float] = None
    key_facts: list[str] = []
    timeline: list[dict] = []
    summary_paragraph: str = ""


class SummarizationService:
    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key
        self._llm = None
        self._prompt_template = None

    def _init_langchain(self):
        try:
            from langchain.chains import LLMChain
            from langchain.prompts import PromptTemplate
            from langchain_community.chat_models import ChatOpenAI

            self._llm = ChatOpenAI(
                model="gpt-4",
                temperature=0.2,
                openai_api_key=self.openai_api_key,
            )
            self._prompt_template = PromptTemplate(
                input_variables=["chat_log"],
                template="""You are a dispute resolution assistant. Summarize the following chat log between a buyer and seller.

Chat log:
{chat_log}

Extract the following information as a JSON object (no markdown, no code fences):
1. "parties": list of the two parties involved (use their addresses or usernames from the chat)
2. "dispute_amount": the monetary amount in dispute as a number (null if not found)
3. "key_facts": list of important factual statements about the dispute
4. "timeline": list of {"timestamp": "description"} objects for key events mentioned
5. "summary_paragraph": a 2-3 sentence summary of the dispute

Return ONLY valid JSON.""",
            )
            self._chain = LLMChain(llm=self._llm, prompt=self._prompt_template)
        except ImportError:
            raise ImportError(
                "langchain and langchain-community required for GPT fallback. "
                "Install with: pip install langchain langchain-community openai"
            )

    def summarize(self, chat_log: str) -> dict:
        if self.openai_api_key:
            return self._summarize_with_llm(chat_log)
        return self._summarize_rule_based(chat_log)

    def _summarize_with_llm(self, chat_log: str) -> dict:
        self._init_langchain()
        try:
            response = self._chain.run(chat_log=chat_log)
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
            data = json.loads(cleaned)
            validated = ChatSummary(**data)
            return validated.model_dump()
        except Exception as e:
            logger.error("LLM summarization failed: %s", e)
            return self._summarize_rule_based(chat_log)

    def _summarize_rule_based(self, chat_log: str) -> dict:
        lines = [l.strip() for l in chat_log.strip().splitlines() if l.strip()]
        parties = []
        amount = None
        key_facts = []

        for line in lines:
            addr = re.findall(r"0x[a-fA-F0-9]{40}", line)
            if addr:
                parties.extend(addr)
            amt = re.findall(r"(\d+(?:\.\d+)?)\s*(?:ETH|eth|usd|USD)", line)
            if amt and amount is None:
                amount = float(amt[0])
            if re.search(r"(claim|say|state|assert|according)", line, re.IGNORECASE):
                key_facts.append(line)

        summary = ChatSummary(
            parties=list(dict.fromkeys(parties))[:2],
            dispute_amount=amount,
            key_facts=key_facts[:5],
            summary_paragraph="Rule-based summary of the dispute chat log.",
        )
        return summary.model_dump()
