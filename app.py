


from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import json
import io
import re
from datetime import datetime
from dotenv import load_dotenv
from openai import AzureOpenAI
import azure.cognitiveservices.speech as speechsdk

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Azure OpenAI credentials
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_API_BASE_URL")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# Azure Speech credentials
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_SUBSCRIPTION_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
)

# Configure Azure Speech
speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
speech_config.speech_synthesis_voice_name = "en-IN-AartiIndicNeural"

# In-memory storage (consider Redis for production)
forms_storage = {}
conversations_storage = {}
current_form = None

# Default form structure
DEFAULT_FORM = {
    "title": "Mutual Fund Application Form",
    "fields": [
        # Distributor Information
        {"name": "ARN", "type": "string", "required": True},
        {"name": "Sub-broker ARN Code", "type": "string", "required": False},
        {"name": "EUIN", "type": "string", "required": True},
        {"name": "RIA Code", "type": "string", "required": False},

        # Applicant Details
        {"name": "Applicant Name", "type": "string", "required": True},
        {"name": "Applicant PAN", "type": "string", "required": True},
        {"name": "Applicant Date of Birth", "type": "date", "required": True},
        {"name": "Applicant Father’s/Spouse’s Name", "type": "string", "required": False},
        {"name": "Applicant Gender", "type": "string", "required": True},
        {"name": "Applicant Marital Status", "type": "string", "required": False},
        {"name": "Applicant Occupation", "type": "string", "required": True},
        {"name": "Mode of Holding", "type": "string", "required": True},
        {"name": "Tax Status", "type": "string", "required": True},
        {"name": "Contact Number – Mobile", "type": "phone", "required": True},
        {"name": "Email ID", "type": "string", "required": True},

        #Mailing Address
        {"name": "Address Line 1", "type": "string", "required": True},
        {"name": "Address Line 2", "type": "string", "required": False},
        {"name": "City", "type": "string", "required": True},
        {"name": "State", "type": "string", "required": True},
        {"name": "Pincode", "type": "string", "required": True},
        {"name": "Country", "type": "string", "required": True},

        # KYC & Income Details
        {"name": "Gross Annual Income", "type": "string", "required": True},
        {"name": "Net Worth", "type": "string", "required": False},
        {"name": "PEP Status", "type": "string", "required": True},
        {"name": "Occupation Type", "type": "string", "required": True},

        # Investment Scheme Selection
        {"name": "Scheme Name", "type": "string", "required": True},
        {"name": "Amount", "type": "number", "required": True},
        {"name": "Mode of Investment", "type": "string", "required": True},

        #Bank Account Details
        {"name": "Bank Name", "type": "string", "required": True},
        {"name": "Branch", "type": "string", "required": True},
        {"name": "Account Number", "type": "string", "required": True},
        {"name": "Account Type", "type": "string", "required": True},
        {"name": "IFSC Code", "type": "string", "required": True},
        {"name": "MICR", "type": "string", "required": True},

        # Investment & Payment Details
        {"name": "Total Investment Amount", "type": "number", "required": True},
        {"name": "Payment Mode", "type": "string", "required": True},
        {"name": "Cheque/DD/UTR No.", "type": "string", "required": False},  # Conditionally required
        {"name": "Payment Bank", "type": "string", "required": True},

        #FATCA/CRS Declaration
        {"name": "Country of Birth", "type": "string", "required": True},
        {"name": "Nationality", "type": "string", "required": True},
        {"name": "Tax Residency Country", "type": "string", "required": True},
        {"name": "Tax Identification No.", "type": "string", "required": False},

        # Nomination Details
        {"name": "Nominee Name", "type": "string", "required": True},
        {"name": "Relationship with Applicant", "type": "string", "required": True},
        {"name": "Nominee Date of Birth", "type": "date", "required": False},  # Conditionally required
        {"name": "Nominee Address", "type": "string", "required": True},
        {"name": "Nominee PAN", "type": "string", "required": False},
        {"name": "Guardian Name", "type": "string", "required": False},  # Conditionally required

        # Declaration & Signature
        
        {"name": "Date of Declaration", "type": "date", "required": True},
        {"name": "Place of Declaration", "type": "string", "required": True}
    ]
}
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/forms', methods=['GET', 'POST'])
def handle_forms():
    global current_form
    
    if request.method == 'POST':
        form_data = request.json
        form_id = str(len(forms_storage) + 1)
        forms_storage[form_id] = form_data
        current_form = form_data
        return jsonify({"success": True, "form_id": form_id, "message": "Form saved successfully!"})
    
    return jsonify({"forms": list(forms_storage.values())})

@app.route('/api/current-form')
def get_current_form():
    global current_form
    if current_form is None:
        current_form = DEFAULT_FORM
    return jsonify(current_form)

@app.route('/api/voice/start-conversation', methods=['POST'])
def start_conversation():
    data = request.json
    form = data.get('form')
    if not form:
        return jsonify({"error": "No form provided"}), 400
    field_names = [field['name'] for field in current_form['fields']]
    #intro_message = f"Hello! I am AutoForm AI. I will help you complete the {form['title']}. Please tell the info:"
    #intro_message=f"Hello! I’ll help you complete your {form['title']}.Just share the details you know. I’ll put them in the form for you and let you review everything at the end.If something’s missing, I’ll simply ask a quick follow-up."
    intro_message = (
    f"Hello! I’ll help you complete your {form['title']}. "
    "Just share the details you know. "
    "I’ll put them in the form for you and let you review everything at the end. "
    "If something’s missing, I’ll simply ask a quick follow-up."
     )
    conversation_id = str(len(conversations_storage) + 1)
    conversations_storage[conversation_id] = {
        "messages": [{"role": "assistant", "content": intro_message}],
        "extracted_data": {},
        "form": form
    }
    
    return jsonify({
        "conversation_id": conversation_id,
        "message": intro_message,
        "success": True
    })

# @app.route('/api/voice/process-speech', methods=['POST'])
# def process_speech():
#     data = request.json
#     conversation_id = data.get('conversation_id')
#     user_input = data.get('text', '')
    
#     if conversation_id not in conversations_storage:
#         return jsonify({"error": "Invalid conversation ID"}), 400
    
#     conversation = conversations_storage[conversation_id]
#     conversation["messages"].append({"role": "user", "content": user_input})
    
#     try:
#         extracted_data = extract_form_data(user_input, conversation["form"], conversation["extracted_data"], conversation["messages"])
#         conversation["extracted_data"].update(extracted_data)
        
#         required_fields = [field['name'] for field in conversation["form"]['fields'] if field['required']]
#         missing_required = [field for field in required_fields if field not in conversation["extracted_data"]]
        
#         if missing_required:
#             fields_to_ask = missing_required[:6]  # Select up to 3 missing fields
#             prompt = f"""
#             You are AutoForm AI, a friendly assistant helping a user fill out a {conversation["form"]["title"]}.
#             Conversation history:
#             {json.dumps(conversation["messages"], indent=2)}
            
#             Current extracted data: {json.dumps(conversation["extracted_data"])}
#             Missing required fields: {', '.join(missing_required)}
            
#             Instructions:
#             - Craft a natural, human-like response asking for the following fields: {', '.join(fields_to_ask)}.
#             - Use the conversation history to make the response context-aware and avoid repeating questions unnecessarily.
#             - Use friendly, conversational language, e.g., "Thanks for that! Could you tell me your {fields_to_ask[0]} and {fields_to_ask[1]}?" (adapt for 1-3 fields).
#             - If only one field is missing, focus on that, e.g., "Great! Could you share your {fields_to_ask[0]}?"
#             - Return only the conversational message.
#             -Do not say this will help us complete the application or similar lines.
#             """
#             response = client.chat.completions.create(
#                 model=AZURE_OPENAI_DEPLOYMENT,
#                 messages=[{"role": "user", "content": prompt}],
#                 temperature=0.7,
#                 max_tokens=100
#             )
#             response_message = response.choices[0].message.content.strip()
#         else:
#             response_message = "Great job! We've collected all the required information. You can now review and submit your form."
        
#         conversation["messages"].append({"role": "assistant", "content": response_message})
        
#         return jsonify({
#             "response": response_message,
#             "extracted_data": conversation["extracted_data"],
#             "all_required_collected": len(missing_required) == 0,
#             "success": True
#         })
        
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
@app.route('/api/voice/process-speech', methods=['POST'])
def process_speech():
    data = request.json
    conversation_id = data.get('conversation_id')
    user_input = data.get('text', '')
    
    if conversation_id not in conversations_storage:
        return jsonify({"error": "Invalid conversation ID"}), 400
    
    conversation = conversations_storage[conversation_id]
    conversation["messages"].append({"role": "user", "content": user_input})
    
    try:
        extracted_data = extract_form_data(user_input, conversation["form"], conversation["extracted_data"], conversation["messages"])
        conversation["extracted_data"].update(extracted_data)
        
        required_fields = [field['name'] for field in conversation["form"]['fields'] if field['required']]
        missing_required = [field for field in required_fields if field not in conversation["extracted_data"]]
        
        if missing_required:
            fields_to_ask = missing_required[:5]  # Select up to 5 missing fields
            # prompt = f"""
            # You are AutoForm AI, a friendly assistant helping a user fill out a {conversation["form"]["title"]}.
            # Conversation history:
            # {json.dumps(conversation["messages"], indent=2)}
            
            # Current extracted data: {json.dumps(conversation["extracted_data"])}
            # Missing required fields: {', '.join(missing_required)}
            
            # Instructions:
            # - Craft a natural, human-like response asking for the following fields: {', '.join(fields_to_ask)}.
            # - Use the conversation history to make the response context-aware and avoid repeating questions unnecessarily.
            # - Use friendly, conversational language, e.g., "Thanks for that! Could you tell me your {fields_to_ask[0]}{' and ' + fields_to_ask[1] if len(fields_to_ask) > 1 else ''}{', ' + fields_to_ask[2] if len(fields_to_ask) > 2 else ''}{', ' + fields_to_ask[3] if len(fields_to_ask) > 3 else ''}{', and ' + fields_to_ask[4] if len(fields_to_ask) > 4 else ''}?"
            # - If only one field is missing, focus on that, e.g., "Great! Could you share your {fields_to_ask[0]}?"
            # - Return only the conversational message.
            # -Do not say this will help us complete the application or similar lines.
            # """
            prompt = f"""
            You are AutoForm AI, a friendly assistant helping a user fill out a {conversation["form"]["title"]}.
            Conversation history:
            {json.dumps(conversation["messages"], indent=2)}
            
            Current extracted data: {json.dumps(conversation["extracted_data"])}
            Missing required fields: {', '.join(missing_required)}
            
            Instructions:
            - Craft a short, natural follow-up asking for the missing fields: {', '.join(fields_to_ask)}.
            - Keep the tone friendly and conversational. For example:
              - If multiple fields are missing: "Thanks! Could you also share the applicant’s gender, occupation, and tax status?"
              - If only one field is missing: "Great! Could you share the applicant’s gender?"
            - Avoid repeating already provided information.
            - Return only the conversational message.
            --Do not say this will help us complete the application or similar lines.
            """

            try:
                response = client.chat.completions.create(
                    model=AZURE_OPENAI_DEPLOYMENT,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=150  # Increased to handle longer prompts
                )
                response_message = response.choices[0].message.content.strip()
                print(f"LLM follow-up response: {response_message}")  # Log for debugging
            except Exception as e:
                print(f"LLM error in generating follow-up: {e}")
                response_message = f"Thanks! Could you provide your {', '.join(fields_to_ask)}?"
        else:
            response_message = "Great job! We've collected all the required information. You can now review and submit your form."
        
        conversation["messages"].append({"role": "assistant", "content": response_message})
        
        return jsonify({
            "response": response_message,
            "extracted_data": conversation["extracted_data"],
            "all_required_collected": len(missing_required) == 0,
            "success": True
        })
        
    except Exception as e:
        print(f"Error in process_speech: {e}, input: {user_input}, conversation_id: {conversation_id}")
        return jsonify({"error": str(e)}), 500

def extract_form_data(text, form_structure, existing_data, conversation_history):
    """Extract form field values from natural language text using Azure OpenAI"""
    
    fields_info = []
    for field in form_structure['fields']:
        field_desc = f"- {field['name']} ({field['type']}, {'required' if field['required'] else 'optional'})"
        fields_info.append(field_desc)
    
    prompt = f"""
    You are AutoForm AI, extracting form field values from user input for a {form_structure['title']}.
    Form fields:
    {chr(10).join(fields_info)}
    
    Conversation history:
    {json.dumps(conversation_history, indent=2)}
    
    Current user input: "{text}"
    Existing extracted data: {json.dumps(existing_data)}
    
    Instructions:
    - Extract all information clearly mentioned in the current user input, using the conversation history for context.
    - For phone numbers, return digits only (remove spaces, dashes, etc.).
    - For dates, format as YYYY-MM-DD if possible.
    - For PAN cards, return alphanumeric characters only.
    - Do not overwrite existing data unless new information explicitly contradicts or updates it.
    - If the input is ambiguous, prioritize the most likely field based on context and field type.
    - Return a JSON object containing only the newly extracted or updated field values.
    """
    
    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500
        )
        
        result_text = response.choices[0].message.content.strip()
        
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            return {}
            
    except Exception as e:
        print(f"Error in data extraction: {e}")
        return {}

@app.route('/api/voice/tts', methods=['POST'])
def text_to_speech():
    data = request.json
    text = data.get('text', '')
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    try:
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        result = synthesizer.speak_text_async(text).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            import base64
            audio_data = base64.b64encode(result.audio_data).decode('utf-8')
            return jsonify({
                "audio_data": audio_data,
                "success": True
            })
        else:
            return jsonify({"error": "Speech synthesis failed"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/submit-form', methods=['POST'])
def submit_form():
    form_data = request.json
    submission_id = str(len(forms_storage) + len(conversations_storage) + 1)
    
    print(f"Form submitted with ID: {submission_id}")
    print(f"Data: {json.dumps(form_data, indent=2)}")
    
    return jsonify({
        "success": True,
        "submission_id": submission_id,
        "message": "Form submitted successfully!"
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
