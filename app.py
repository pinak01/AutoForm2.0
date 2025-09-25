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

# In-memory storage
forms_storage = {}
conversations_storage = {}
current_form = None

# Default form structure
# DEFAULT_FORM = {
#     "title": "Personal Information Form",
#     "fields": [
#         {"name": "Name", "type": "string", "required": True},
#         {"name": "Phone Number", "type": "phone", "required": True},
#         {"name": "Date of Birth", "type": "date", "required": True},
#         {"name": "PAN Card", "type": "string", "required": False},
#         {"name": "Address", "type": "string", "required": False}
#     ]
# }
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
        {"name": "PAN", "type": "string", "required": True},
        {"name": "Date of Birth", "type": "date", "required": True},
        {"name": "Father’s/Spouse’s Name", "type": "string", "required": False},
        {"name": "Gender", "type": "string", "required": True},
        {"name": "Marital Status", "type": "string", "required": False},
        {"name": "Occupation", "type": "string", "required": True},
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
        {"name": "Plan", "type": "string", "required": True},
        {"name": "Option", "type": "string", "required": True},
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
        {"name": "Date", "type": "date", "required": True},
        {"name": "Bank Name (Payment)", "type": "string", "required": True},

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
        
        {"name": "Date (Declaration)", "type": "date", "required": True},
        {"name": "Place", "type": "string", "required": True}
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

# @app.route('/api/voice/start-conversation', methods=['POST'])
# def start_conversation():
#     global current_form
#     if current_form is None:
#         current_form = DEFAULT_FORM
    
#     # Create introduction message
#     field_names = [field['name'] for field in current_form['fields']]
#     #intro_message = f"Hello! I am AutoForm AI. I will help you complete the {current_form['title']}. Please tell me your {', '.join(field_names)}."
#     intro_message = f"Hello! I am AutoForm AI. I will help you complete the {current_form['title']}. Please tell the info:"
#     # Initialize conversation
#     conversation_id = str(len(conversations_storage) + 1)
#     conversations_storage[conversation_id] = {
#         "messages": [{"role": "assistant", "content": intro_message}],
#         "extracted_data": {},
#         "form": current_form
#     }
    
#     return jsonify({
#         "conversation_id": conversation_id,
#         "message": intro_message,
#         "success": True
#     })
@app.route('/api/voice/start-conversation', methods=['POST'])
def start_conversation():
    data = request.json  # Add this to parse the sent JSON body
    form = data.get('form')  # Use the sent form instead of global

    if not form:  # Fallback if somehow not sent (though it should be)
        return jsonify({"error": "No form provided"}), 400

    # Create introduction message (use 'form' instead of 'current_form')
    field_names = [field['name'] for field in form['fields']]
    intro_message = f"Hello! I am AutoForm AI. I will help you complete the {form['title']}. Please tell the info:"

    # Initialize conversation
    conversation_id = str(len(conversations_storage) + 1)
    conversations_storage[conversation_id] = {
        "messages": [{"role": "assistant", "content": intro_message}],
        "extracted_data": {},
        "form": form  # Store the sent form here
    }
    
    return jsonify({
        "conversation_id": conversation_id,
        "message": intro_message,
        "success": True
    })

@app.route('/api/voice/process-speech', methods=['POST'])
def process_speech():
    data = request.json
    conversation_id = data.get('conversation_id')
    user_input = data.get('text', '')
    
    if conversation_id not in conversations_storage:
        return jsonify({"error": "Invalid conversation ID"}), 400
    
    conversation = conversations_storage[conversation_id]
    conversation["messages"].append({"role": "user", "content": user_input})
    
    # Extract data using Azure OpenAI
    try:
        extracted_data = extract_form_data(user_input, conversation["form"], conversation["extracted_data"])
        conversation["extracted_data"].update(extracted_data)
        
        # Check if all required fields are collected
        required_fields = [field['name'] for field in conversation["form"]['fields'] if field['required']]
        missing_required = [field for field in required_fields if field not in conversation["extracted_data"]]
        
        if missing_required:
            # Ask for missing required fields
            response_message = f"I still need the following information: {', '.join(missing_required)}. Could you please provide them?"
        else:
            # All required fields collected
            response_message = "Thank you! I have collected all the required information. You can now proceed to review and submit the form."
        
        conversation["messages"].append({"role": "assistant", "content": response_message})
        
        return jsonify({
            "response": response_message,
            "extracted_data": conversation["extracted_data"],
            "all_required_collected": len(missing_required) == 0,
            "success": True
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def extract_form_data(text, form_structure, existing_data):
    """Extract form field values from natural language text using Azure OpenAI"""
    
    fields_info = []
    for field in form_structure['fields']:
        field_desc = f"- {field['name']} ({field['type']}, {'required' if field['required'] else 'optional'})"
        fields_info.append(field_desc)
    
    prompt = f"""
    Extract form field values from the following user input. The form has these fields:
    {chr(10).join(fields_info)}
    
    User input: "{text}"
    
    Currently extracted data: {json.dumps(existing_data)}
    
    Instructions:
    - Extract only the information that is clearly mentioned in the user input
    - For phone numbers, extract digits only (remove spaces, dashes, etc.)
    - For dates, format as YYYY-MM-DD if possible
    - For PAN cards, extract alphanumeric characters only
    - Don't overwrite existing data unless new information is provided
    - Return only new or updated field values
    
    Respond with a JSON object containing only the extracted field values:
    """
    
    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Extract JSON from the response
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
        # Create speech synthesizer
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        
        # Synthesize speech
        result = synthesizer.speak_text_async(text).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            # Return audio data as base64
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
    
    # Save submitted form (in real app, this would go to database)
    submission_id = str(len(forms_storage) + len(conversations_storage) + 1)
    
    # Here you would typically save to database
    print(f"Form submitted with ID: {submission_id}")
    print(f"Data: {json.dumps(form_data, indent=2)}")
    
    return jsonify({
        "success": True,
        "submission_id": submission_id,
        "message": "Form submitted successfully!"
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)