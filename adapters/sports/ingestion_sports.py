# Stub for legacy compatibility
class SportsIngestor:
    def __init__(self, *args, **kwargs):
        self.errors = []
        self.lineage = []
        self.source_name = args[0] if args else "SportsIngestor"
        self.last_resolutions = []
    def record_error(self, stage, e):
        self.errors.append({
            "stage": stage,
            "error": str(e),
            "timestamp": "stub"
        })
    def record_lineage(self, stage, metadata=None):
        entry = {
            "stage": stage,
            "timestamp": "stub",
            "source": self.source_name
        }
        if metadata:
            entry["details"] = metadata
        self.lineage.append(entry)
    def connect(self):
        pass
    def apply_semantic_layer(self, df):
        # Stub: return df unchanged and record a dummy resolution
        self.last_resolutions.append({"field": "engine_temp", "resolution": "noop"})
        return df
    def run(self):
        return []
