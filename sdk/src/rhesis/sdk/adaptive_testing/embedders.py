import appdirs
import diskcache
import numpy as np
from sklearn.preprocessing import normalize

from rhesis.sdk import adaptive_testing

_embedding_memory_cache = {}
_embedding_file_cache = diskcache.Cache(
    appdirs.user_cache_dir("adaptive_testing") + "/embeddings.diskcache"
)


def _embed(strings, normalize=True):
    # find which strings are not in the cache
    new_text_strings = []
    new_image_urls = []
    text_prefix = (
        _text_embedding_model().name
    )  # TODO: need to figure out how to do the same for image embedding, but only when needed
    for s in strings:
        if s.startswith("__IMAGE="):
            prefixed_s = s
        else:
            prefixed_s = text_prefix + s
        if prefixed_s not in _embedding_memory_cache:
            if prefixed_s not in _embedding_file_cache:
                if s.startswith("__IMAGE="):
                    new_image_urls.append(s)
                else:
                    new_text_strings.append(s)
                _embedding_memory_cache[prefixed_s] = (
                    None  # so we don't embed the same string twice
                )
            else:
                _embedding_memory_cache[prefixed_s] = _embedding_file_cache[prefixed_s]

    # embed the new text strings
    if len(new_text_strings) > 0:
        new_embeds = _text_embedding_model()(new_text_strings)
        for i, s in enumerate(new_text_strings):
            prefixed_s = text_prefix + s
            if normalize:
                _embedding_memory_cache[prefixed_s] = new_embeds[i] / np.linalg.norm(new_embeds[i])
            else:
                _embedding_memory_cache[prefixed_s] = new_embeds[i]
            _embedding_file_cache[prefixed_s] = _embedding_memory_cache[prefixed_s]

    # embed the new image urls
    if len(new_image_urls) > 0:
        new_embeds = _image_embedding_model()([url[8:] for url in new_image_urls])
        for i, s in enumerate(new_image_urls):
            if normalize:
                _embedding_memory_cache[s] = new_embeds[i] / np.linalg.norm(new_embeds[i])
            else:
                _embedding_memory_cache[s] = new_embeds[i]
            _embedding_file_cache[s] = _embedding_memory_cache[s]

    return [
        _embedding_memory_cache[s if s.startswith("__IMAGE=") else text_prefix + s] for s in strings
    ]


def _text_embedding_model():
    """Get the text embedding model.

    Much of this code block is from the sentence_transformers documentation.
    """
    if adaptive_testing.text_embedding_model is None:
        # # get the modules we need to compute embeddings
        # import torch
        # import transformers

        # # Mean Pooling - Take attention mask into account for correct averaging
        # def mean_pooling(model_output, attention_mask):
        #     token_embeddings = model_output[0] # First element of model_output contains all token embeddings
        #     input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        #     return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

        # # Load model from HuggingFace Hub
        # tokenizer = transformers.AutoTokenizer.from_pretrained('sentence-transformers/stsb-roberta-base-v2')
        # model = transformers.AutoModel.from_pretrained('sentence-transformers/stsb-roberta-base-v2')

        # # Tokenize sentences
        # def embed_model(sentences):
        #     encoded_input = tokenizer(sentences, padding=True, truncation=True, return_tensors='pt')

        #     # Compute token embeddings
        #     with torch.no_grad():
        #         model_output = model(**encoded_input)

        #     # Perform pooling. In this case, max pooling.
        #     return mean_pooling(model_output, encoded_input['attention_mask']).cpu().numpy()

        adaptive_testing.text_embedding_model = TransformersTextEmbedding()

    return adaptive_testing.text_embedding_model


def _image_embedding_model():
    if adaptive_testing.image_embedding_model is None:
        import clip  # pylint: disable=import-outside-toplevel
        import torch

        model, preprocess = clip.load("ViT-L/14", device="cpu", jit=True)

        def embed_model(urls):
            with torch.no_grad():
                out = []
                for url in urls:
                    image = adaptive_testing.utils.get_image(url)
                    image_emb = model.encode_image(preprocess(image).unsqueeze(0).to("cpu"))
                    image_emb /= image_emb.norm(dim=-1, keepdim=True)
                    image_emb = image_emb.cpu().detach().numpy().astype("float32")[0]
                    out.append(image_emb)
            return np.vstack(out)

        adaptive_testing.image_embedding_model = embed_model

    return adaptive_testing.image_embedding_model


def cos_sim(a, b):
    """Cosine distance between two vectors."""
    return normalize(a, axis=1) @ normalize(b, axis=1).T


class TransformersTextEmbedding:
    def __init__(self, model="sentence-transformers/stsb-roberta-base-v2"):
        import transformers

        self.tokenizer = transformers.AutoTokenizer.from_pretrained(model)
        self.model = transformers.AutoModel.from_pretrained(model)
        self.model_name = model
        self.name = "adaptive_testing.embedders.TransformersTextEmbedding(" + self.model_name + "):"

    def __call__(self, strings):
        import torch

        encoded_input = self.tokenizer(strings, padding=True, truncation=True, return_tensors="pt")

        # Compute token embeddings
        with torch.no_grad():
            model_output = self.model(**encoded_input)

        # Perform mean pooling
        token_embeddings = model_output[
            0
        ]  # First element of model_output contains all token embeddings
        input_mask_expanded = (
            encoded_input["attention_mask"].unsqueeze(-1).expand(token_embeddings.size()).float()
        )
        embeds = torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
            input_mask_expanded.sum(1), min=1e-9
        )
        return embeds.cpu().numpy()


class OpenAITextEmbedding:
    def __init__(self, model="text-similarity-babbage-001", api_key=None, replace_newlines=True):
        self.api_key = api_key
        self.model = model
        self.replace_newlines = replace_newlines
        self.model_name = model
        self.name = "adaptive_testing.embedders.OpenAITextEmbedding(" + self.model_name + "):"

    def __call__(self, strings):
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)

        if len(strings) == 0:
            return np.array([])

        # clean the strings for OpenAI
        cleaned_strings = []
        for s in strings:
            if s == "":
                s = " "  # because OpenAI doesn't like empty strings
            elif self.replace_newlines:
                s = s.replace("\n", " ")  # OpenAI recommends this for things that are not code
            cleaned_strings.append(s)

        # call the OpenAI API to complete the prompts
        response = client.embeddings.create(input=cleaned_strings, model=self.model, user="adatest")

        return np.vstack([e.embedding for e in response.data])
