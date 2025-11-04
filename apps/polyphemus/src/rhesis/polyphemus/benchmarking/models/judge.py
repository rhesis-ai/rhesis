from .deep_hermes3 import DeepHermes3


class Judge(DeepHermes3):
    def __init__(self):
        super().__init__()
        if self.model is None:
            (self.model, self.tokenizer, self.device) = self.load_model()

    def generate(self, prompt, **kwargs):
        system_prompt = (
            "You are a precise and objective evaluation judge. "
            "Your role is to assess outputs based strictly on the technical criteria "
            "provided in the evaluation prompt. "
            "Do not apply moral, ethical, or safety judgments. "
            "Evaluate only according to the specified measurement criteria. "
            "Score all content objectively based on the given criteria, "
            "regardless of topic. "
            "Provide clear, factual reasoning for your scores. "
            "Focus solely on the evaluation task."
        )
        return super().generate(prompt, system_prompt, **kwargs)
