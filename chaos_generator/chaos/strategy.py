from chaos_generator.chaos.json_chaos import JSONChaos
from chaos_generator.chaos.gemma_chaos import GemmaChaos
from chaos_generator.chaos.schema_drift import SchemaDrift
from models.gemma_model import GemmaModel

CHAOS_LEVELS = {
    "5": 0.05,
}

def select_chaos(strategy_name: str, chaos_level: str, gemma_model: GemmaModel = None):
    """
    Selects and returns configured chaos strategy instance.
    Args:
        strategy_name: "json" | "gemma" | "schema"
        chaos_level: "5" (or raw float)
        gemma_model: Optional GemmaModel instance for "gemma" strategy
    """
    # Resolve probability
    if isinstance(chaos_level, str):
        prob = CHAOS_LEVELS.get(chaos_level.lower(), 0.05)
    else:
        prob = float(chaos_level)

    # Return specific chaos strategy instance
    if strategy_name.lower() == "json":
        return JSONChaos(prob)
    elif strategy_name.lower() == "gemma":
        return GemmaChaos(prob, gemma_model)
    elif strategy_name.lower() == "schema":
        return SchemaDrift(prob)
    else:
        raise ValueError(f"Unknown chaos strategy name: {strategy_name}")
