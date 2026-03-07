# backend/model_manager.py
class ModelManager:
    def __init__(self):
        self.models = {
            'mistral-7b': MistralDoctorAssistant(),
            'llama-2-7b': LlamaDoctorAssistant(),
            'medical-llama': MedicalLlamaAssistant(),
            'lightweight': TinyMedicalAssistant()  # For low-resource systems
        }
        self.current_model = 'mistral-7b'
    
    def switch_model(self, model_name):
        if model_name in self.models:
            self.current_model = model_name
            return True
        return False
    
    def generate_response(self, prompt):
        return self.models[self.current_model].generate_response(prompt)