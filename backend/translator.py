# backend/translator.py
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

class MedicalTranslator:
    def __init__(self):
        self.model = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_418M")
        self.tokenizer = M2M100Tokenizer.from_pretrained("facebook/m2m100_418M")
        
    def translate(self, text, src_lang, tgt_lang):
        self.tokenizer.src_lang = src_lang
        encoded = self.tokenizer(text, return_tensors="pt")
        generated_tokens = self.model.generate(**encoded, forced_bos_token_id=self.tokenizer.get_lang_id(tgt_lang))
        return self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]