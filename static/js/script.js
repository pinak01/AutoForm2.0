let currentForm = null;
        let conversationId = null;
        let recognition = null;
        let isListening = false;
        let extractedData = {};
        let accumulatedTranscript = '';  // Store all speech until stop is clicked

        // Initialize the application
        document.addEventListener('DOMContentLoaded', function() {
            loadDefaultForm();
        });

        // Navigation functions
        function showSection(sectionId) {
            const sections = document.querySelectorAll('.section');
            const navBtns = document.querySelectorAll('.nav-btn');
            
            sections.forEach(section => section.classList.remove('active'));
            navBtns.forEach(btn => btn.classList.remove('active'));
            
            document.getElementById(sectionId + '-section').classList.add('active');
            event.target.classList.add('active');
        }

        // Form Builder Functions
        function loadDefaultForm() {
            fetch('/api/current-form')
                .then(response => response.json())
                .then(data => {
                    currentForm = data;
                    document.getElementById('form-title').value = data.title;
                    renderFields();
                })
                .catch(error => console.error('Error loading form:', error));
        }

        function renderFields() {
            const fieldsContainer = document.getElementById('fields-list');
            fieldsContainer.innerHTML = '';

            currentForm.fields.forEach((field, index) => {
                const fieldDiv = document.createElement('div');
                fieldDiv.className = 'field-item';
                fieldDiv.innerHTML = `
                    <input type="text" class="field-input" value="${field.name}" 
                           onchange="updateField(${index}, 'name', this.value)" placeholder="Field name">
                    <select class="field-type" onchange="updateField(${index}, 'type', this.value)">
                        <option value="string" ${field.type === 'string' ? 'selected' : ''}>String</option>
                        <option value="phone" ${field.type === 'phone' ? 'selected' : ''}>Phone</option>
                        <option value="date" ${field.type === 'date' ? 'selected' : ''}>Date</option>
                    </select>
                    <div class="checkbox-container">
                        <input type="checkbox" id="required-${index}" ${field.required ? 'checked' : ''} 
                               onchange="updateField(${index}, 'required', this.checked)">
                        <label for="required-${index}">Required</label>
                    </div>
                    <button class="remove-btn" onclick="removeField(${index})">Remove</button>
                `;
                fieldsContainer.appendChild(fieldDiv);
            });
        }

        function addField() {
            if (!currentForm) currentForm = { title: '', fields: [] };
            
            currentForm.fields.push({
                name: 'New Field',
                type: 'string',
                required: false
            });
            renderFields();
        }

        function updateField(index, property, value) {
            if (currentForm && currentForm.fields[index]) {
                currentForm.fields[index][property] = value;
            }
        }

        function removeField(index) {
            if (currentForm && currentForm.fields) {
                currentForm.fields.splice(index, 1);
                renderFields();
            }
        }

        function saveForm() {
            const title = document.getElementById('form-title').value;
            if (!title.trim()) {
                showMessage('save-message', 'Please enter a form title', 'error');
                return;
            }

            if (!currentForm.fields || currentForm.fields.length === 0) {
                showMessage('save-message', 'Please add at least one field', 'error');
                return;
            }

            currentForm.title = title;

            fetch('/api/forms', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(currentForm)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage('save-message', data.message, 'success');
                } else {
                    showMessage('save-message', 'Error saving form', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('save-message', 'Error saving form', 'error');
            });
        }

        // Voice Agent Functions
        function startVoiceAgent() {
            if (!currentForm) {
                alert('Please create and save a form first');
                return;
            }

            updateVoiceStatus('Initializing voice agent...', 'processing');
            
            fetch('/api/voice/start-conversation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ form: currentForm })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    conversationId = data.conversation_id;
                    addMessage('assistant', data.message);
                    
                    // Speak the introduction
                    speakText(data.message);
                    
                    // Enable start listening button, disable start agent
                    document.getElementById('start-agent-btn').disabled = true;
                    document.getElementById('start-listening-btn').disabled = false;
                    
                    updateVoiceStatus('Voice agent ready. Click "Start Listening" when you want to speak.', 'waiting');
                } else {
                    updateVoiceStatus('Error starting voice agent', 'waiting');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                updateVoiceStatus('Error starting voice agent', 'waiting');
            });
        }

        function startListening() {
            if (!conversationId) {
                alert('Please start the voice agent first');
                return;
            }

            // Reset accumulated transcript
            accumulatedTranscript = '';
            
            // Initialize and start speech recognition
            initializeSpeechRecognition();
            
            // Update button states
            document.getElementById('start-listening-btn').disabled = true;
            document.getElementById('stop-listening-btn').disabled = false;
            
            updateVoiceStatus('Listening... Speak now! Click "Stop Listening" when done.', 'listening');
        }

        function initializeSpeechRecognition() {
            if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
                alert('Speech recognition not supported in this browser');
                return;
            }

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = 'en-US';

            recognition.onstart = function() {
                isListening = true;
                updateVoiceStatus('Listening... Speak continuously! Click "Stop Listening" when finished.', 'listening');
            };

            recognition.onresult = function(event) {
                let interimTranscript = '';
                let finalTranscript = '';
                
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript;
                    } else {
                        interimTranscript += event.results[i][0].transcript;
                    }
                }

                if (finalTranscript) {
                    accumulatedTranscript += finalTranscript + ' ';
                }

                // Show real-time transcript (optional - you can remove this if you don't want to show interim results)
                if (interimTranscript) {
                    updateVoiceStatus(`Listening... Current: "${interimTranscript.trim()}"`, 'listening');
                }
            };

            recognition.onerror = function(event) {
                console.error('Speech recognition error:', event.error);
                updateVoiceStatus('Speech recognition error. Click "Start Listening" to try again.', 'waiting');
                resetListeningButtons();
            };

            recognition.onend = function() {
                if (isListening) {
                    // Auto-restart if we're still supposed to be listening
                    try {
                        recognition.start();
                    } catch (e) {
                        console.log('Recognition restart failed:', e);
                        resetListeningButtons();
                    }
                }
            };

            // Start listening
            recognition.start();
        }

        function stopListening() {
            if (recognition) {
                isListening = false;
                recognition.stop();
            }
            
            // Process the accumulated transcript
            if (accumulatedTranscript.trim()) {
                updateVoiceStatus('Processing your complete speech...', 'processing');
                processSpeech(accumulatedTranscript.trim());
            } else {
                updateVoiceStatus('No speech detected. Click "Start Listening" to try again.', 'waiting');
                resetListeningButtons();
            }
        }

        function resetListeningButtons() {
            document.getElementById('start-listening-btn').disabled = false;
            document.getElementById('stop-listening-btn').disabled = true;
        }

        function processSpeech(text) {
            if (!conversationId) return;

            updateVoiceStatus('AI is analyzing your complete speech...', 'processing');
            addMessage('user', text);

            fetch('/api/voice/process-speech', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    conversation_id: conversationId,
                    text: text
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addMessage('assistant', data.response);
                    speakText(data.response);
                    
                    // Update extracted data
                    if (data.extracted_data) {
                        extractedData = data.extracted_data;
                        updateExtractedDataDisplay();
                    }
                    
                    // Check if all required fields are collected
                    if (data.all_required_collected) {
                        updateVoiceStatus('All required information collected! You can now review the form.', 'waiting');
                        showFormPreview();
                        // Keep buttons ready for new conversation
                        resetListeningButtons();
                    } else {
                        updateVoiceStatus('AI response complete. Click "Start Listening" to provide more information.', 'waiting');
                        resetListeningButtons();
                    }
                } else {
                    updateVoiceStatus('Error processing speech. Please try again.', 'waiting');
                    resetListeningButtons();
                }
            })
            .catch(error => {
                console.error('Error:', error);
                updateVoiceStatus('Error processing speech. Please try again.', 'waiting');
                resetListeningButtons();
            });
        }

        function speakText(text) {
            fetch('/api/voice/tts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: text })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success && data.audio_data) {
                    // Play the audio
                    const audio = new Audio('data:audio/wav;base64,' + data.audio_data);
                    audio.play();
                }
            })
            .catch(error => console.error('TTS Error:', error));
        }

        function updateVoiceStatus(message, status) {
            const statusElement = document.getElementById('voice-status');
            statusElement.textContent = message;
            statusElement.className = `voice-status status-${status}`;
        }

        function addMessage(sender, message) {
            const conversationLog = document.getElementById('conversation-log');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender}`;
            messageDiv.innerHTML = `<strong>${sender === 'assistant' ? 'AI' : 'You'}:</strong> ${message}`;
            conversationLog.appendChild(messageDiv);
            conversationLog.scrollTop = conversationLog.scrollHeight;
        }

        function updateExtractedDataDisplay() {
            const dataContainer = document.getElementById('extracted-data');
            const dataPreview = document.getElementById('data-preview');
            
            if (Object.keys(extractedData).length > 0) {
                dataContainer.style.display = 'block';
                let html = '<div style="background: #f8f9fa; padding: 1rem; border-radius: 8px;">';
                
                for (const [key, value] of Object.entries(extractedData)) {
                    html += `<div style="margin-bottom: 0.5rem;"><strong>${key}:</strong> ${value}</div>`;
                }
                
                html += '</div>';
                dataPreview.innerHTML = html;
            }
        }

        // Form Preview Functions
        function showFormPreview() {
            if (!currentForm || Object.keys(extractedData).length === 0) return;
            
            // Show the preview navigation button
            document.getElementById('preview-nav').style.display = 'inline-block';
            
            const previewContainer = document.getElementById('form-preview-container');
            let html = `<h3>${currentForm.title}</h3><div class="form-preview">`;
            
            currentForm.fields.forEach(field => {
                const value = extractedData[field.name] || '';
                const required = field.required ? '<span class="required">*</span>' : '';
                
                html += `
                    <div class="form-group">
                        <label>${field.name}${required}</label>
                        <input type="${getInputType(field.type)}" 
                               id="preview-${field.name.replace(/\s+/g, '-')}" 
                               value="${value}" 
                               ${field.required ? 'required' : ''}>
                    </div>
                `;
            });
            
            html += `
                </div>
                <div style="margin-top: 2rem; text-align: center;">
                    <button class="btn btn-success" onclick="submitForm()">Submit Form</button>
                </div>
                <div id="submit-message"></div>
            `;
            
            previewContainer.innerHTML = html;
            
            // Auto-switch to preview section
            showSection('form-preview');
        }

        function getInputType(fieldType) {
            switch (fieldType) {
                case 'date':
                    return 'date';
                case 'phone':
                    return 'tel';
                default:
                    return 'text';
            }
        }

        function submitForm() {
            const formData = {};
            
            currentForm.fields.forEach(field => {
                const inputId = `preview-${field.name.replace(/\s+/g, '-')}`;
                const inputElement = document.getElementById(inputId);
                
                if (inputElement) {
                    formData[field.name] = inputElement.value;
                }
            });
            
            // Validate required fields
            const missingRequired = [];
            currentForm.fields.forEach(field => {
                if (field.required && (!formData[field.name] || formData[field.name].trim() === '')) {
                    missingRequired.push(field.name);
                }
            });
            
            if (missingRequired.length > 0) {
                showMessage('submit-message', `Please fill in required fields: ${missingRequired.join(', ')}`, 'error');
                return;
            }
            
            // Submit the form
            fetch('/api/submit-form', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    form_title: currentForm.title,
                    data: formData,
                    timestamp: new Date().toISOString()
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage('submit-message', `Form submitted successfully! Submission ID: ${data.submission_id}`, 'success');
                    
                    // Reset the application after successful submission
                    setTimeout(() => {
                        resetApplication();
                    }, 3000);
                } else {
                    showMessage('submit-message', 'Error submitting form', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('submit-message', 'Error submitting form', 'error');
            });
        }

        function resetApplication() {
            // Reset all variables
            conversationId = null;
            extractedData = {};
            isListening = false;
            accumulatedTranscript = '';
            
            // Reset UI
            document.getElementById('conversation-log').innerHTML = '';
            document.getElementById('extracted-data').style.display = 'none';
            document.getElementById('form-preview-container').innerHTML = '';
            document.getElementById('preview-nav').style.display = 'none';
            
            // Reset voice controls to initial state
            document.getElementById('start-agent-btn').disabled = false;
            document.getElementById('start-listening-btn').disabled = true;
            document.getElementById('stop-listening-btn').disabled = true;
            updateVoiceStatus('Click "Start Voice Agent" to begin', 'waiting');
            
            // Stop recognition if active
            if (recognition) {
                recognition.stop();
                recognition = null;
            }
            
            // Go back to form builder
            showSection('form-builder');
            
            // Reload default form
            loadDefaultForm();
        }

        // Utility Functions
        function showMessage(elementId, message, type) {
            const element = document.getElementById(elementId);
            element.innerHTML = `<div class="${type}-message">${message}</div>`;
            
            // Clear message after 5 seconds
            setTimeout(() => {
                element.innerHTML = '';
            }, 5000);
        }

        // Handle page reload/close
        window.addEventListener('beforeunload', function() {
            if (isListening && recognition) {
                recognition.stop();
            }
        });
