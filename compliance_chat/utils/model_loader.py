import os
import sys
import json
from dotenv import load_dotenv
from compliance_chat.utils.config_loader import load_config
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from compliance_chat.logger import GLOBAL_LOGGER as log
from compliance_chat.exception.custom_exception import DocumentPortalException



class ApiKeyManager:
    REQUIRED_KEYS = ["OPENAI_API_KEY", "PINECONE_API_KEY", "TAVILY_API_KEY"]
    OPTIONAL_KEYS = ["COHERE_API_KEY"]

    def __init__(self):
        self.api_keys = {}
        raw = os.getenv("apikeyliveclass")

        if raw:
            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("API_KEYS is not a valid JSON object")
                self.api_keys = parsed
                log.info("Loaded API_KEYS from ECS secret")
            except Exception as e:
                log.warning("Failed to parse API_KEYS as JSON", error=str(e))




        for key in self.REQUIRED_KEYS + self.OPTIONAL_KEYS:
            if not self.api_keys.get(key):
                env_val = os.getenv(key)
                if env_val:
                    self.api_keys[key] = env_val
                    log.info(f"Loaded {key} from individual env var")

        # Final check
        missing = [k for k in self.REQUIRED_KEYS if not self.api_keys.get(k)]
        if missing:
            log.error("Missing required API keys", missing_keys=missing)
            raise DocumentPortalException("Missing API keys")

        log.info("API keys loaded", keys={k: v[:6] + "..." for k, v in self.api_keys.items()})


    def get(self, key: str) -> str:
        val = self.api_keys.get(key)
        if not val:
            raise KeyError(f"API key for {key} is missing")
        return val


class ModelLoader:
    """
    Loads embedding models and LLMs based on config and environment.
    """

    def __init__(self):
        if os.getenv("ENV", "local").lower() != "production":
            load_dotenv()
            log.info("Running in LOCAL mode: .env loaded")
        else:
            log.info("Running in PRODUCTION mode")

        self.api_key_mgr = ApiKeyManager()
        self.config = load_config()
        log.info("YAML config loaded", config_keys=list(self.config.keys()))

        # Initialize Pinecone
        self._init_pinecone()
        
        # Initialize Cohere
        self._init_cohere()

    def _init_cohere(self):
        """Initialize Cohere client."""
        try:
            import cohere
            api_key = self.api_key_mgr.api_keys.get("COHERE_API_KEY")
            if not api_key:
                log.warning("COHERE_API_KEY not found in environment (reranking disabled)")
                self.cohere_client = None
                return
            self.cohere_client = cohere.ClientV2(api_key=api_key)
            log.info("Cohere client initialized")
        except Exception as e:
            log.warning("Failed to initialize Cohere (reranking will be disabled)", error=str(e))
            self.cohere_client = None

    def load_bm25_encoder(self):
        """Load the pre-fitted BM25 encoder from the compliance_project directory."""
        import pickle
        from pathlib import Path
        
        # Priority: Check for bm25_encoder.pkl in current the research/output or compliance_project path
        # Assuming the structure provided in the metadata
        base_path = Path(r"d:\Deltone Solutions\scraping\compliance_project")
        cache_path = base_path / "research" / "output" / "bm25_encoder.pkl"
        
        if not cache_path.exists():
            # Fallback to a relative path if the absolute one fails
            cache_path = Path("compliance_chat/research/output/bm25_encoder.pkl")

        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    log.info("BM25 encoder loaded successfully", path=str(cache_path))
                    return pickle.load(f)
            except Exception as e:
                log.error("Failed to load BM25 encoder", error=str(e))
                return None
        else:
            log.warning("BM25 encoder not found", path=str(cache_path))
            return None

    def _init_pinecone(self):
        """Initialize Pinecone client."""
        try:
            from pinecone import Pinecone

            api_key = self.api_key_mgr.get("PINECONE_API_KEY")
            self.pc = Pinecone(api_key=api_key)

            log.info("Pinecone client initialized")
        except Exception as e:
            log.error("Failed to initialize Pinecone", error=str(e))
            raise DocumentPortalException("Pinecone initialization error", sys)

    def get_pinecone_index_name(self) -> str:
        """Get Pinecone index name from config."""
        return self.config.get("pinecone", {}).get("index_name", "risksafeai-index")


    def load_embeddings(self):
        """
        Load and return OpenAI embedding model (text-embedding-3-large).
        """
        try:
            model_name = self.config["embedding_model"]["model_name"]
            log.info("Loading embedding model", model=model_name)
            return OpenAIEmbeddings(
                model=model_name,
                openai_api_key=self.api_key_mgr.get("OPENAI_API_KEY")
            )
        except Exception as e:
            log.error("Error loading embedding model", error=str(e))
            raise DocumentPortalException("Failed to load embedding model", sys)

    def load_llm(self):
        """
        Load and return OpenAI ChatGPT model (gpt-4o).
        """
        llm_block = self.config["llm"]
        provider_key = os.getenv("LLM_PROVIDER", "openai")

        if provider_key not in llm_block:
            log.error("LLM provider not found in config", provider=provider_key)
            raise ValueError(f"LLM provider '{provider_key}' not found in config")

        llm_config = llm_block[provider_key]
        provider = llm_config.get("provider")
        model_name = llm_config.get("model_name")
        temperature = llm_config.get("temperature", 0)
        max_tokens = llm_config.get("max_output_tokens", 4000)

        log.info("Loading LLM", provider=provider, model=model_name)

        if provider == "openai":
            return ChatOpenAI(
                model=model_name,
                api_key=self.api_key_mgr.get("OPENAI_API_KEY"),
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            log.error("Unsupported LLM provider", provider=provider)
            raise ValueError(f"Unsupported LLM provider: {provider}")


if __name__ == "__main__":
    loader = ModelLoader()

    # Test Embedding
    embeddings = loader.load_embeddings()
    print(f"Embedding Model Loaded: {embeddings}")
    result = embeddings.embed_query("Hello, how are you?")
    print(f"Embedding Result: {result}")

    # Test LLM
    llm = loader.load_llm()
    print(f"LLM Loaded: {llm}")
    result = llm.invoke("Hello, how are you?")
    print(f"LLM Result: {result.content}")
