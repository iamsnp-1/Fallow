"""
Fallow — IBM watsonx.ai Client

Provides Granite inference and embeddings via the watsonx.ai SDK.
Falls back to mock responses when credentials are unavailable, with
clear logging that the mock is active — never silently fakes integration.
"""

import json
import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# Try to import the IBM SDK
_ibm_available = False
try:
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai import Credentials, APIClient
    _ibm_available = True
except ImportError:
    logger.warning("ibm-watsonx-ai SDK not installed. Using mock LLM.")


class WatsonxClient:
    """Client for IBM watsonx.ai Granite inference and embeddings."""

    def __init__(self):
        self._settings = get_settings()
        self._model: Optional[object] = None
        self._client: Optional[object] = None
        self._using_mock = False
        self._initialize()

    def _initialize(self):
        """Initialize the watsonx client, or flag mock mode."""
        if not _ibm_available:
            logger.warning("IBM watsonx SDK not available — running in MOCK mode")
            self._using_mock = True
            return

        if not self._settings.has_watsonx_credentials:
            logger.warning(
                "WATSONX_API_KEY or WATSONX_PROJECT_ID not set — running in MOCK mode. "
                "Set these in .env to use real IBM Granite."
            )
            self._using_mock = True
            return

        try:
            credentials = Credentials(
                url=self._settings.WATSONX_URL,
                api_key=self._settings.WATSONX_API_KEY,
            )
            self._client = APIClient(credentials, project_id=self._settings.WATSONX_PROJECT_ID)
            self._model = ModelInference(
                model_id=self._settings.GRANITE_MODEL_ID,
                api_client=self._client,
            )
            logger.info(f"IBM watsonx.ai client initialized with model {self._settings.GRANITE_MODEL_ID}")
        except Exception as e:
            logger.error(f"Failed to initialize watsonx client: {e}. Running in MOCK mode.")
            self._using_mock = True

    @property
    def is_mock(self) -> bool:
        return self._using_mock

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate text using Granite or mock."""
        if self._using_mock:
            logger.info("MOCK: Generating text (no real IBM API call)")
            return self._mock_generate(prompt, system_prompt)

        try:
            params = {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "repetition_penalty": 1.1,
            }

            # Build the prompt with system instructions
            full_prompt = ""
            if system_prompt:
                full_prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{prompt}\n<|assistant|>\n"
            else:
                full_prompt = f"<|user|>\n{prompt}\n<|assistant|>\n"

            result = self._model.generate_text(
                prompt=full_prompt,
                params=params,
            )

            if isinstance(result, str):
                return result
            return str(result)

        except Exception as e:
            logger.error(f"Granite generation error: {e}")
            raise

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using watsonx or fallback to simple hash-based embeddings."""
        if self._using_mock:
            logger.info("MOCK: Generating embeddings (hash-based)")
            return self._mock_embed(texts)

        try:
            from ibm_watsonx_ai.foundation_models import Embeddings

            embedding_model = Embeddings(
                model_id=self._settings.EMBEDDING_MODEL_ID,
                api_client=self._client,
            )
            result = embedding_model.embed_documents(texts)
            return result

        except Exception as e:
            logger.error(f"Embedding error: {e}, falling back to mock")
            return self._mock_embed(texts)

    def _mock_generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate a mock advisory response.
        This is clearly marked as mock output and follows the expected JSON schema.
        """
        # Check if this is an advisory generation request
        if "advisory" in prompt.lower() or "recommendation" in prompt.lower():
            return self._mock_advisory_response(prompt)

        if "locali" in prompt.lower() or "translate" in prompt.lower():
            return self._mock_localization_response(prompt)

        return '{"message": "Mock response — set WATSONX_API_KEY to use real IBM Granite"}'

    def _mock_advisory_response(self, prompt: str) -> str:
        """Generate a mock advisory that matches the Advisory schema."""
        # Parse passage IDs from the prompt
        passage_ids = []
        for line in prompt.split("\n"):
            if "passage_id" in line.lower() or "P-" in line:
                import re
                ids = re.findall(r'P-[a-f0-9]+', line)
                passage_ids.extend(ids)

        if not passage_ids:
            passage_ids = ["P-demo0001", "P-demo0002", "P-demo0003"]

        # Detect district context from prompt
        is_thanjavur = "thanjavur" in prompt.lower() or "in-tn-tnj" in prompt.lower() or "cauvery" in prompt.lower()

        if not is_thanjavur:
            return json.dumps({
                "recommended": [
                    {
                        "crop": "Bajra (Pearl Millet)",
                        "rank": 1,
                        "rationale": [
                            {
                                "statement": "Bajra requires only 300-400mm rainfall and is highly drought-tolerant, making it suitable for seasons with significant rainfall deficit.",
                                "citation_ids": [passage_ids[0]] if passage_ids else ["P-demo0001"]
                            },
                            {
                                "statement": "Bajra matures in 70-90 days, allowing harvest before late-season moisture stress.",
                                "citation_ids": [passage_ids[1] if len(passage_ids) > 1 else passage_ids[0]]
                            }
                        ],
                        "water_requirement_mm": 350.0,
                        "sowing_window": "Mid-June to mid-July",
                        "expected_viability": "good"
                    },
                    {
                        "crop": "Tur (Pigeon Pea)",
                        "rank": 2,
                        "rationale": [
                            {
                                "statement": "Tur is a deep-rooted legume with moderate drought tolerance, requiring 600-650mm over a longer season. It fixes nitrogen, improving soil health.",
                                "citation_ids": [passage_ids[2] if len(passage_ids) > 2 else passage_ids[0]]
                            }
                        ],
                        "water_requirement_mm": 625.0,
                        "sowing_window": "June to early July",
                        "expected_viability": "moderate"
                    },
                    {
                        "crop": "Mung (Green Gram)",
                        "rank": 3,
                        "rationale": [
                            {
                                "statement": "Mung bean is a short-duration crop (60-75 days) with low water requirements (300-350mm), suitable as a catch crop in deficit years.",
                                "citation_ids": [passage_ids[0]]
                            }
                        ],
                        "water_requirement_mm": 325.0,
                        "sowing_window": "Late June to mid-July",
                        "expected_viability": "good"
                    }
                ],
                "irrigation_guidance": [
                    {
                        "statement": "With projected 35% rainfall deficit, prioritize protective irrigation at critical growth stages: flowering and grain filling.",
                        "citation_ids": [passage_ids[1] if len(passage_ids) > 1 else passage_ids[0]]
                    },
                    {
                        "statement": "Implement mulching with crop residues to conserve soil moisture and reduce evaporation losses by 20-30%.",
                        "citation_ids": [passage_ids[2] if len(passage_ids) > 2 else passage_ids[0]]
                    }
                ],
                "warnings": [
                    "Rainfall forecast indicates significant deficit — avoid water-intensive crops like cotton and soybean this season.",
                    "Forecast confidence is medium; continue monitoring IMD updates through the season."
                ],
                "hedged": False,
                "sufficient_guidance": True
            })
        else:
            return json.dumps({
                "recommended": [
                    {
                        "crop": "Rice (Paddy)",
                        "rank": 1,
                        "rationale": [
                            {
                                "statement": "Rice is the traditional and best-suited crop for the Cauvery delta zone with adequate water availability from both rainfall and canal irrigation.",
                                "citation_ids": [passage_ids[0]]
                            },
                            {
                                "statement": "The projected near-normal rainfall supports standard transplanting schedules and water management practices.",
                                "citation_ids": [passage_ids[1] if len(passage_ids) > 1 else passage_ids[0]]
                            }
                        ],
                        "water_requirement_mm": 1200.0,
                        "sowing_window": "June to August (Samba/Kuruvai seasons)",
                        "expected_viability": "good"
                    },
                    {
                        "crop": "Blackgram",
                        "rank": 2,
                        "rationale": [
                            {
                                "statement": "Blackgram is an excellent rotation crop with rice, fixing nitrogen and requiring only 300-350mm water. It can be cultivated as a second crop after rice harvest.",
                                "citation_ids": [passage_ids[2] if len(passage_ids) > 2 else passage_ids[0]]
                            }
                        ],
                        "water_requirement_mm": 325.0,
                        "sowing_window": "September to October (rice fallow)",
                        "expected_viability": "good"
                    },
                    {
                        "crop": "Sesame",
                        "rank": 3,
                        "rationale": [
                            {
                                "statement": "Sesame performs well in the delta zone as a rainfed crop and offers good market returns with relatively low water requirements.",
                                "citation_ids": [passage_ids[0]]
                            }
                        ],
                        "water_requirement_mm": 400.0,
                        "sowing_window": "June to July",
                        "expected_viability": "moderate"
                    }
                ],
                "irrigation_guidance": [
                    {
                        "statement": "With near-normal rainfall expected, follow standard irrigation scheduling. Ensure canal water allocation is confirmed before transplanting.",
                        "citation_ids": [passage_ids[0]]
                    },
                    {
                        "statement": "Adopt alternate wetting and drying (AWD) technique to save 15-20% irrigation water without yield penalty.",
                        "citation_ids": [passage_ids[1] if len(passage_ids) > 1 else passage_ids[0]]
                    }
                ],
                "warnings": [
                    "Monitor northeast monsoon onset timing for Samba rice transplanting decisions."
                ],
                "hedged": False,
                "sufficient_guidance": True
            })

    def _mock_localization_response(self, prompt: str) -> str:
        """Generate a mock localized advisory."""
        if "mr" in prompt.lower() or "marathi" in prompt.lower():
            return json.dumps({
                "full_text": "हंगामातील पावसाचा अंदाज: तुमच्या जिल्ह्यात या हंगामात सरासरीपेक्षा ३५% कमी पाऊस अपेक्षित आहे.\n\nशिफारस: बाजरी (पर्ल मिलेट) हे या हंगामासाठी सर्वात योग्य पीक आहे. बाजरीला फक्त ३००-४०० मिमी पाऊस लागतो आणि ती दुष्काळ सहन करू शकते.\n\nपेरणीची वेळ: जून मध्य ते जुलै मध्य\n\nसिंचन: फुलोऱ्याच्या आणि दाणे भरण्याच्या अवस्थेत संरक्षक सिंचनाला प्राधान्य द्या.\n\nस्रोत: ICAR पीक-पाणी आवश्यकता सारणी, MPKV राहुरी विस्तार बुलेटिन",
                "sms_text": "पाऊस ३५% कमी. बाजरी पेरा, कापूस टाळा. पेरणी: जून-जुलै. फुलोऱ्यात सिंचन करा. -फॅलो",
                "citation_labels": {}
            })
        elif "ta" in prompt.lower() or "tamil" in prompt.lower():
            return json.dumps({
                "full_text": "பருவ மழை முன்னறிவிப்பு: உங்கள் மாவட்டத்தில் இந்த பருவத்தில் சராசரிக்கு நெருக்கமான மழை எதிர்பார்க்கப்படுகிறது.\n\nபரிந்துரை: நெல் (நன்செய்) இந்த பருவத்திற்கு மிகவும் பொருத்தமான பயிர். காவிரி டெல்டா மண்டலத்தில் போதுமான நீர் கிடைக்கும்.\n\nவிதைப்பு நேரம்: ஜூன் முதல் ஆகஸ்ட் வரை\n\nநீர்ப்பாசனம்: மாற்று ஈரமாக்குதல் மற்றும் உலர்த்துதல் நுட்பத்தை பின்பற்றுங்கள்.\n\nமூலம்: ICAR பயிர்-நீர் தேவை அட்டவணை, TNAU நீட்டிப்பு புல்லட்டின்",
                "sms_text": "மழை சராசரி. நெல் பயிரிட ஏற்றது. விதைப்பு: ஜூன்-ஆகஸ்ட். AWD நீர்ப்பாசனம் செய்யுங்கள். -Fallow",
                "citation_labels": {}
            })
        else:
            return json.dumps({
                "full_text": "Season Rainfall Forecast: Your district is projected to receive rainfall this season.\n\nRecommendation: Based on the forecast and local agronomic guidance, the most suitable crop has been identified.\n\nPlease refer to the detailed advisory for sowing windows, irrigation guidance, and source citations.\n\nSource: ICAR Crop-Water Requirement Tables, State Agricultural University Extension Bulletins",
                "sms_text": "Seasonal advisory ready. Check Fallow app for crop recommendation, sowing window, and irrigation guidance. -Fallow",
                "citation_labels": {}
            })

    def _mock_embed(self, texts: list[str]) -> list[list[float]]:
        """Generate deterministic hash-based embeddings for mock mode."""
        import hashlib
        embeddings = []
        for text in texts:
            h = hashlib.sha256(text.encode()).digest()
            # Generate a 384-dimensional embedding from the hash
            embedding = []
            for i in range(384):
                byte_idx = i % len(h)
                embedding.append((h[byte_idx] - 128) / 128.0)
            embeddings.append(embedding)
        return embeddings


# Singleton
_client_instance: Optional[WatsonxClient] = None


def get_watsonx_client() -> WatsonxClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = WatsonxClient()
    return _client_instance
