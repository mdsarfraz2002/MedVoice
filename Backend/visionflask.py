from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import threading
import time
import speech_recognition as sr
import queue
import json
from twilio.rest import Client
import requests


app = Flask(__name__, static_folder="./frontend_build/static", template_folder="./frontend_build")
CORS(app)

# Use environment variables for sensitive information
sender_email = "visiontech@candle.engineer"
sender_password = "temp@123"
mailgun_api_key = "0527e9d7f185a7e48fa5d069a7512d87-5d2b1caa-dca0a72d"
mailgun_domain = "candle.engineer"
account_sid = 
auth_token = '49bde32f861d4718dfd325e462fdf017'
twilio_phone_number = '+14154841582'

# Global variables
listening = False
progress_thread = None
patient_id = ""
patient_name = ""
patient_age = ""
patient_gender = ""
patient_contact = ""
transcript_queue = queue.Queue()
prescriptions_list = []
notes_list = []


# Flask route for rendering the main page
@app.route('/')
def index():
    return render_template('index.html')

'''# Error handling for 404 - Not Found
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# Error handling for 500 - Internal Server Error
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500'''

# Function to handle speech recognition
def listen_thread(mode):
    global listening
    r = sr.Recognizer()
    with sr.Microphone() as source:
        while listening:
            audio_text = r.listen(source)
            try:
                transcript = r.recognize_google(audio_text)
                transcript_queue.put((mode, transcript))
            except Exception as e:
                transcript_queue.put((mode, "Sorry, I didn't get that"))
            time.sleep(1)

# Function to update transcript
def update_transcript():
    while not transcript_queue.empty():
        mode, transcript = transcript_queue.get()
        if transcript != "Stopped listening":
            if "Sorry, I didn't get that" not in transcript:
                # Handle transcript update as needed
                print(f"[{mode.capitalize()}]: {transcript}")
                if mode.lower() == "prescription":
                    prescriptions_list.append(transcript + "\n")
                elif mode.lower() == "note":
                    notes_list.append(transcript + "\n")
    # Schedule the next update
    threading.Timer(1, update_transcript).start()

# Function to start listening
def start_listen(mode):
    global listening, progress_thread
    listening = True
    # Start a new thread to handle speech recognition
    progress_thread = threading.Thread(target=listen_thread, args=(mode,))
    progress_thread.start()

# Function to stop listening
def stop_listen():
    global listening, progress_thread
    listening = False
    # Give some time for the listen_thread to finish
    time.sleep(1)
    # Wait for the progress thread to finish
    if progress_thread:
        progress_thread.join()

# Function to save patient information
def save_patient_info(id_var, name_var, age_var, gender_var, contact_var):
    global patient_id, patient_name, patient_age, patient_gender, patient_contact
    patient_id = id_var
    patient_name = name_var
    patient_age = age_var
    patient_gender = gender_var
    patient_contact = contact_var

# Function to save data to JSON
def save_data_to_json():
    global patient_id, patient_name, patient_age, patient_gender, patient_contact, prescriptions_list, notes_list
    try:
        # Try to read existing data from the file
        with open("medical_record.json", "r") as json_file:
            existing_data = json.load(json_file)
    except FileNotFoundError:
        # If the file doesn't exist, create an empty dictionary
        existing_data = {}

    # Use patient_id as the primary key
    existing_data[patient_id] = {
        "patient_name": patient_name,
        "patient_age": patient_age,
        "patient_gender": patient_gender,
        "patient_contact": patient_contact,
        "prescriptions": prescriptions_list,
        "notes": notes_list
    }

    try:
        # Write the updated data back to the file
        with open("medical_record.json", "w") as json_file:
            json.dump(existing_data, json_file, indent=4)
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'failure', 'error': str(e)}

# Flask route to start prescription recording
@app.route('/start_prescription_record', methods=['POST'])
def start_prescription_record_route():
    mode = "prescription"
    start_listen(mode)
    return jsonify({'status': 'success'})

# Flask route to start notes recording
@app.route('/start_notes_record', methods=['POST'])
def start_notes_record_route():
    mode = "note"
    start_listen(mode)
    return jsonify({'status': 'success'})

# Flask route to stop listening
@app.route('/stop_listening', methods=['POST'])
def stop_listening_route():
    stop_listen()
    return jsonify({'status': 'success'})

# Flask route to input patient details
@app.route('/patient_detail', methods=['POST'])
def patient_detail_route():
    try:
        data = request.json
        save_patient_info(data['patient_id'], data['patient_name'], data['patient_age'], data['patient_gender'], data['patient_contact'])
        return jsonify({'status': 'success'})
    except KeyError as e:
        return jsonify({'status': 'error', 'message': f'Missing required field: {str(e)}'})

# Flask route to view transcript
@app.route('/view_transcript', methods=['GET'])
def view_transcript_route():
    global patient_id, patient_name, patient_age, patient_gender, patient_contact, prescriptions_list, notes_list
    return jsonify({
        'patient_id': patient_id,
        'patient_name': patient_name,
        'patient_age': patient_age,
        'patient_gender': patient_gender,
        'patient_contact': patient_contact,
        'prescriptions': prescriptions_list,
        'notes': notes_list
    })

# Flask route to save data to JSON
@app.route('/save_data_to_json', methods=['POST'])
def save_data_to_json_route():
    result = save_data_to_json()
    return jsonify(result)

# Flask route to send email
@app.route('/send_email', methods=['POST'])
def send_email_route():
    subject = "Speech Recognition Transcript"
    body = f"Patient ID: {patient_id}\n" \
           f"Patient Name: {patient_name}\n" \
           f"Patient Age: {patient_age}\n" \
           f"Patient Gender: {patient_gender}\n" \
           f"Patient Contact Number: {patient_contact}\n" \
           f"Prescription: {''.join(prescriptions_list)}\n" \
           f"Notes: {''.join(notes_list)}"

    recipient_email = request.json.get('recipient_email', '')
    if recipient_email:
        # Mailgun API URL
        mailgun_url = f"https://api.mailgun.net/v3/{mailgun_domain}/messages"

        # Data for the Mailgun API call
        data = {
            "from": sender_email,
            "to": recipient_email,
            "subject": subject,
            "text": body
        }

        # Authentication for the Mailgun API call
        auth = ("api", mailgun_api_key)

        try:
            # Make the Mailgun API call
            response = requests.post(mailgun_url, auth=auth, data=data)
            response.raise_for_status()  # Raise an error for HTTP errors

            return jsonify({'status': 'success', 'message': 'Email sent successfully!'})
        except requests.exceptions.RequestException as e:
            print(f"Error sending email: {e}")
            return jsonify({'status': 'error', 'message': 'Failed to send email. Check console for details.'})
    else:
        return jsonify({'status': 'error', 'message': 'Recipient email not provided.'})

# Flask route to send SMS
@app.route('/send_sms', methods=['POST'])
def send_sms_route():
    phone_number = request.json.get('phone_number', '')
    if phone_number:
        client = Client(account_sid, auth_token)
        message_body = f"Patient ID: {patient_id}\n" \
                       f"Patient Name: {patient_name}\n" \
                       f"Patient Age: {patient_age}\n" \
                       f"Patient Gender: {patient_gender}\n" \
                       f"Patient Contact Number: {patient_contact}\n" \
                       f"Prescription: {''.join(prescriptions_list)}\n" \
                       f"Notes: {''.join(notes_list)}"

        try:
            message = client.messages.create(
                from_=twilio_phone_number,
                body=message_body,
                to=phone_number
            )
            return jsonify({'status': 'success', 'message': f'SMS sent successfully! SID: {message.sid}'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Failed to send SMS. Error: {e}'})
    else:
        return jsonify({'status': 'error', 'message': 'Invalid phone number.'})

# Flask route to share options
@app.route('/share', methods=['POST'])
def share_route():
    save_data_to_json()
    
    sharing_options = {
        'mail': {'text': 'Mail', 'color': '#3498DB'},
        'sms': {'text': 'SMS', 'color': '#E74C3C'}
    }

    return jsonify({'status': 'success', 'options': sharing_options})

# Flask route to handle the selected sharing option
@app.route('/handle_share_option', methods=['POST'])
def handle_share_option():
    save_data_to_json()

    option = request.json.get('option')

    if option == 'mail':
        result = send_email_route()
    elif option == 'sms':
        result = send_sms_route()
    else:
        result = {'status': 'error', 'message': 'Invalid sharing option'}

    return jsonify(result)

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True,port=3000)
