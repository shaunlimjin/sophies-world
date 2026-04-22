from scripts.providers.model_providers.base import ModelProvider

def test_model_provider_is_abc():
    try:
        provider = ModelProvider()
        raise AssertionError("ModelProvider cannot be instantiated directly")
    except TypeError:
        pass  # ABC raises TypeError

def test_model_provider_name_property():
    """Subclasses must implement the name property."""
    class DummyProvider(ModelProvider):
        @property
        def name(self):
            return "dummy"

        def generate(self, prompt: str, **kwargs) -> dict:
            return {"result": ""}

    p = DummyProvider({})
    assert p.name == "dummy"
