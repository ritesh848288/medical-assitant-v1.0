import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MistralDoctorAssistant:
    def __init__(self, model_name="mistralai/Mistral-7B-Instruct-v0.2"):
        self.model_name = model_name
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.tokenizer = None
        self.load_model()
        
    def load_model(self):
        """Load Mistral model locally"""
        try:
            logger.info(f"Loading Mistral model on {self.device}...")
            
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto",
                trust_remote_code=True,
                low_cpu_mem_usage=True
            )
            
            logger.info("Model loaded successfully!")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
    
    def generate_response(self, user_input, conversation_history=[], context=None):
        """Generate medical response using Mistral"""
        try:
            system_prompt = """You are DoctorAI, a professional medical assistant. 
            Important guidelines:
            - Provide accurate medical information
            - Always include appropriate disclaimers
            - Identify emergency situations
            - Recommend seeing real doctors when necessary
            - Be compassionate and professional
            - Use clear, understandable language
            """
            
            if context:
                system_prompt += f"\nContext: {context}"
            
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history
            for msg in conversation_history[-10:]:
                messages.append(msg)
            
            messages.append({"role": "user", "content": user_input})
            
            # Apply chat template
            prompt = self.tokenizer.apply_chat_template(
                messages, 
                tokenize=False,
                add_generation_prompt=True
            )
            
            # Tokenize
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=512,
                    temperature=0.7,
                    do_sample=True,
                    top_p=0.95,
                    repetition_penalty=1.1,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode response
            response = self.tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I apologize, but I'm having trouble processing your request. Please try again."
    
    def analyze_symptoms(self, symptoms_list, user_info=None):
        """Analyze symptoms and provide assessment"""
        context = f"Patient age: {user_info.get('age', 'unknown')}, Gender: {user_info.get('gender', 'unknown')}"
        symptoms_text = ", ".join(symptoms_list)
        
        prompt = f"""Based on the following symptoms: {symptoms_text}
        
        Please provide:
        1. Possible conditions (with disclaimer)
        2. Severity assessment (Low/Medium/High/Emergency)
        3. Recommended actions
        4. When to see a doctor
        5. Home care suggestions if applicable
        """
        
        return self.generate_response(prompt, context=context)